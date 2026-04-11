import logging
from datetime import timedelta
from itertools import cycle

from django.utils import timezone
from django.db import transaction
from django.core.mail import EmailMultiAlternatives
from django_q.tasks import async_task

from api.leads.models import Lead
from api.lead_status.models import LeadStatus
from api.leads_task.models import LeadTask
from api.leads_task_type.models import LeadTaskType
from api.users.models import User
from api.users.roles import UserRoles
from api.leads_task.constants import LeadTaskStatus, LeadTaskPriority
from api.leads.constants import (
    PRESENT,
    ABSENT,
    ANNULE,
    RDV_CONFIRME,
    RDV_PLANIFIE,
)

from api.sms.tasks import (
    send_absent_urgency_sms_task,
    send_appointment_reminder_48h_sms_task,
    send_appointment_reminder_24h_sms_task,
)
from api.utils.email.leads.tasks import (
    send_appointment_absent_email_task,
    send_appointment_reminder_email_task,
)

logger = logging.getLogger(__name__)

# ⚙️ Adresse email du rapport journalier — modifie ici
RAPPORT_EMAIL = "marc.takoumba@papiers-express.fr"


# =========================================================
# 1. GESTION DES ABSENCES (DÉTECTION + NOTIFICATION)
# =========================================================

def mark_missed_appointments_as_absent():
    now = timezone.now()

    try:
        absent_status = LeadStatus.objects.get(code=ABSENT)
    except LeadStatus.DoesNotExist:
        logger.error("❌ Status ABSENT non trouvé dans la base")
        return "0 leads updated - Status ABSENT missing"

    leads_qs = Lead.objects.filter(
        appointment_date__isnull=False,
        appointment_date__lt=now,
    ).exclude(
        status__code__in=[PRESENT, ABSENT, ANNULE]
    )

    lead_ids = list(leads_qs.values_list("id", flat=True))

    if not lead_ids:
        logger.info("✅ Aucun nouveau rendez-vous manqué détecté.")
        return "0 leads marked as absent"

    try:
        with transaction.atomic():
            updated_count = leads_qs.update(status=absent_status)

        for lead_id in lead_ids:
            async_task(send_absent_urgency_sms_task, lead_id)
            async_task(send_appointment_absent_email_task, lead_id)
            logger.info(f"📢 Notifications d'absence mises en file pour le lead #{lead_id}")

        return f"{updated_count} leads passés en ABSENT."

    except Exception as e:
        logger.error(f"❌ Erreur lors de la mise à jour massive : {str(e)}")
        return f"Error: {str(e)}"


# =========================================================
# 2. CRÉATION DES TÂCHES CRM (POUR L'ACCUEIL)
# =========================================================

def create_absent_followup_tasks(limit_per_user_per_day=20):
    now = timezone.now()

    task_type, _ = LeadTaskType.objects.get_or_create(
        code="RELANCE_ABSENT",
        defaults={
            "label": "Relance client absent",
            "description": "Appeler le client pour reprogrammer un rendez-vous.",
        },
    )

    accueil_users = list(User.objects.filter(role=UserRoles.ACCUEIL, is_active=True))
    if not accueil_users:
        logger.warning("⚠️ Aucun agent d'accueil actif.")
        return "Abort: No active ACCUEIL users"

    active_tasks_leads = LeadTask.objects.filter(
        task_type=task_type,
        status=LeadTaskStatus.TODO
    ).values_list('lead_id', flat=True)

    leads_to_process = Lead.objects.filter(
        status__code=ABSENT,
        appointment_date__isnull=False,
    ).exclude(id__in=active_tasks_leads).order_by('-appointment_date')

    if not leads_to_process.exists():
        return "No new tasks to create"

    num_agents = len(accueil_users)
    user_pool = cycle(accueil_users)
    daily_capacity = num_agents * limit_per_user_per_day
    created_count = 0

    with transaction.atomic():
        for index, lead in enumerate(leads_to_process):
            days_offset = index // daily_capacity
            scheduled_date = now + timedelta(days=days_offset)
            agent = next(user_pool)

            LeadTask.objects.create(
                lead=lead,
                task_type=task_type,
                title=f"Relancer {lead.first_name} {lead.last_name}",
                description=f"Rendez-vous manqué le {lead.appointment_date.strftime('%d/%m/%Y')}.",
                due_at=scheduled_date,
                assigned_to=agent,
                status=LeadTaskStatus.TODO,
                priority=LeadTaskPriority.MEDIUM,
            )
            created_count += 1

    return f"{created_count} internal tasks created."


# =========================================================
# 3. RAPPELS DE RENDEZ-VOUS (AVANT LE RDV)
# =========================================================

def send_appointment_reminders():
    now = timezone.now()
    tolerance = timedelta(minutes=10)

    reminder_windows = [
        (timedelta(hours=48), "48h", send_appointment_reminder_48h_sms_task),
        (timedelta(hours=24), "24h", send_appointment_reminder_24h_sms_task),
    ]

    total_sent = 0

    for delta, label, sms_task_func in reminder_windows:
        target_time = now + delta

        leads = Lead.objects.filter(
            appointment_date__gte=target_time - tolerance,
            appointment_date__lte=target_time + tolerance,
            status__code__in=[RDV_CONFIRME, RDV_PLANIFIE],
        )

        for lead in leads:
            if lead.last_reminder_sent and (now - lead.last_reminder_sent) < timedelta(hours=20):
                continue

            async_task(sms_task_func, lead.id)
            async_task(send_appointment_reminder_email_task, lead.id)

            lead.last_reminder_sent = now
            lead.save(update_fields=["last_reminder_sent"])

            total_sent += 1
            logger.info(f"✅ Rappel {label} mis en file pour le lead #{lead.id}")

    return f"{total_sent} reminders sent"


# =========================================================
# 4. RAPPORT JOURNALIER
# =========================================================

def send_daily_report():
    """
    Envoie un rapport journalier à RAPPORT_EMAIL avec :
    - Les leads passés en ABSENT dans les dernières 24h
    - Les leads qui ont reçu un rappel dans les dernières 24h
    Planifier ce job tous les jours à 20h00 dans Django-Q.
    """
    now = timezone.now()
    since = now - timedelta(hours=24)
    today_str = now.strftime("%d/%m/%Y")

    # ── Absents détectés aujourd'hui ─────────────────────────
    absents = Lead.objects.filter(
        status__code=ABSENT,
        appointment_date__gte=since,
        appointment_date__lt=now,
    ).select_related("status")

    absents_data = [
        {
            "name": f"{l.first_name} {l.last_name}",
            "phone": l.phone or "—",
            "email": l.email or "—",
            "appointment_date": l.appointment_date.strftime("%d/%m/%Y à %H:%M") if l.appointment_date else "—",
        }
        for l in absents
    ]

    # ── Rappels envoyés aujourd'hui ───────────────────────────
    rappels = Lead.objects.filter(
        last_reminder_sent__gte=since,
        last_reminder_sent__lte=now,
    ).select_related("status")

    rappels_data = [
        {
            "name": f"{l.first_name} {l.last_name}",
            "phone": l.phone or "—",
            "email": l.email or "—",
            "appointment_date": l.appointment_date.strftime("%d/%m/%Y à %H:%M") if l.appointment_date else "—",
            "status": l.status.label if l.status else "—",
        }
        for l in rappels
    ]

    stats = {
        "total_absents": len(absents_data),
        "total_rappels": len(rappels_data),
        "date": today_str,
        "heure": now.strftime("%H:%M"),
    }

    logger.info(
        "📊 Rapport journalier : %d absents, %d rappels",
        stats["total_absents"], stats["total_rappels"],
    )

    html = _build_report_html(stats, absents_data, rappels_data)

    try:
        msg = EmailMultiAlternatives(
            subject=f"📊 Rapport journalier Papiers Express – {today_str}",
            body=f"Rapport du {today_str} : {stats['total_absents']} absents, {stats['total_rappels']} rappels.",
            from_email="Papiers Express <noreply@papiers-express.fr>",
            to=[RAPPORT_EMAIL],
        )
        msg.attach_alternative(html, "text/html")
        msg.send()
        logger.info("✅ Rapport journalier envoyé à %s", RAPPORT_EMAIL)
        return f"Rapport envoyé : {stats['total_absents']} absents, {stats['total_rappels']} rappels"
    except Exception as e:
        logger.error("❌ Erreur envoi rapport : %s", str(e))
        return f"Erreur : {str(e)}"


def _build_report_html(stats: dict, absents: list, rappels: list) -> str:

    def _rows(data: list, cols: list) -> str:
        if not data:
            return f'<tr><td colspan="{len(cols)}" style="text-align:center;color:#888;padding:12px">Aucun</td></tr>'
        rows = ""
        for i, row in enumerate(data):
            bg = "#f9f9f9" if i % 2 == 0 else "#ffffff"
            cells = "".join(
                f'<td style="padding:8px 12px;border-bottom:1px solid #eee">{row.get(c, "—")}</td>'
                for c in cols
            )
            rows += f'<tr style="background:{bg}">{cells}</tr>'
        return rows

    absent_rows = _rows(absents, ["name", "phone", "email", "appointment_date"])
    rappel_rows = _rows(rappels, ["name", "phone", "email", "appointment_date", "status"])

    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto;padding:20px;color:#333">

  <div style="background:#1a1a2e;color:white;padding:24px;border-radius:10px 10px 0 0;text-align:center">
    <h1 style="margin:0;font-size:22px">📊 Rapport Journalier</h1>
    <p style="margin:8px 0 0;opacity:0.8">Papiers Express – {stats['date']} à {stats['heure']}</p>
  </div>

  <div style="display:flex;border:1px solid #eee;border-top:none">
    <div style="flex:1;padding:20px;text-align:center;border-right:1px solid #eee">
      <div style="font-size:36px;font-weight:bold;color:#ff4d4f">{stats['total_absents']}</div>
      <div style="color:#666;font-size:14px;margin-top:4px">Absents détectés</div>
    </div>
    <div style="flex:1;padding:20px;text-align:center">
      <div style="font-size:36px;font-weight:bold;color:#1677ff">{stats['total_rappels']}</div>
      <div style="color:#666;font-size:14px;margin-top:4px">Rappels envoyés</div>
    </div>
  </div>

  <div style="margin-top:24px">
    <h2 style="font-size:16px;border-left:4px solid #ff4d4f;padding-left:10px;margin-bottom:12px">
      ❌ Leads absents ({stats['total_absents']})
    </h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead>
        <tr style="background:#fff1f0;color:#cf1322">
          <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #ffa39e">Nom</th>
          <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #ffa39e">Téléphone</th>
          <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #ffa39e">Email</th>
          <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #ffa39e">Date RDV</th>
        </tr>
      </thead>
      <tbody>{absent_rows}</tbody>
    </table>
  </div>

  <div style="margin-top:24px">
    <h2 style="font-size:16px;border-left:4px solid #1677ff;padding-left:10px;margin-bottom:12px">
      🔔 Rappels envoyés ({stats['total_rappels']})
    </h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead>
        <tr style="background:#e6f4ff;color:#0958d9">
          <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #91caff">Nom</th>
          <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #91caff">Téléphone</th>
          <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #91caff">Email</th>
          <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #91caff">Date RDV</th>
          <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #91caff">Statut</th>
        </tr>
      </thead>
      <tbody>{rappel_rows}</tbody>
    </table>
  </div>

  <div style="margin-top:32px;padding:16px;background:#f5f5f5;border-radius:0 0 10px 10px;text-align:center;font-size:12px;color:#999">
    Papiers Express – 39 rue Navier, 75017 Paris<br>
    Rapport généré automatiquement tous les jours à 20h00.
  </div>

</body>
</html>"""