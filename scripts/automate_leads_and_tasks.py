import os
import sys
import django
import logging
import re
from datetime import timedelta

# 🔧 1. Initialisation Django (AVANT LES IMPORTS)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
try:
    django.setup()
except Exception as e:
    print(f"❌ Erreur d'initialisation de Django : {e}")
    sys.exit(1)

from django.utils import timezone
from django.db import transaction

# Imports des modèles et constantes
from api.leads.models import Lead, LeadStatus
from api.users.models import User
from api.users.roles import UserRoles
from api.leads_task.models import LeadTask
from api.leads_task.constants import LeadTaskStatus
from api.leads_task_type.models import LeadTaskType
from api.leads_events.models import LeadEvent

# Imports Celery
from api.sms.tasks import send_absent_urgency_sms_task

# 👇 Remplace par ta vraie tâche d'envoi d'email pour les absents si elle a un autre nom
# from api.utils.email.leads.tasks import send_absent_email_task

# Configuration du Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configurable : Nombre de tâches max par jour par utilisateur
TASKS_PER_DAY_MIN = 7
TASKS_PER_DAY_MAX = 10


def get_or_create_task_type(code, label, dry_run=False):
    if dry_run:
        return None  # En mode test, on ne crée pas le type en DB
    tt, _ = LeadTaskType.objects.get_or_create(code=code, defaults={'label': label, 'is_active': True})
    return tt


def is_french_number(phone):
    """Vérifie si un numéro est français (+33, 0033, ou format local 06, 07...)."""
    if not phone:
        return False
    # Nettoyer les espaces, tirets et points
    cleaned = re.sub(r'[\s\-\.]', '', str(phone))
    # Regex : Commence par +33 ou 0033 suivi de 9 chiffres, OU commence par 0 suivi de 9 chiffres
    return bool(re.match(r'^(?:\+33|0033)\d{9}$|^0\d{9}$', cleaned))


def run(dry_run=True):
    now = timezone.now()
    mode_text = "🧪 MODE TEST (DRY RUN) - AUCUNE MODIFICATION" if dry_run else "🚀 MODE PRODUCTION - EXÉCUTION RÉELLE"

    logger.info("=" * 60)
    logger.info(mode_text)
    logger.info("=" * 60)

    # 1️⃣ Récupération des utilisateurs ACCUEIL actifs
    accueil_users = list(User.objects.filter(role=UserRoles.ACCUEIL, is_active=True))
    if not accueil_users:
        logger.error("❌ Aucun utilisateur ACCUEIL actif trouvé. Fin du script.")
        return

    num_users = len(accueil_users)
    logger.info(f"👥 {num_users} agents d'accueil détectés pour la répartition.")

    # 2️⃣ Identification des leads qui ont manqué leur RDV
    leads_to_mark_absent = Lead.objects.filter(
        appointment_date__lt=now,
    ).exclude(status__code__in=["ABSENT", "PRESENT", "CONTRAT_SIGNE"])

    total_absents = leads_to_mark_absent.count()
    logger.info(f"🔍 {total_absents} leads détectés comme potentiellement absents.\n")

    task_type = get_or_create_task_type("RELANCE_ABSENT", "Relance suite absence RDV", dry_run)
    absent_status = LeadStatus.objects.filter(code="ABSENT").first()

    counter = 0
    for lead in leads_to_mark_absent:
        # --- ANALYSE DES CONDITIONS ---
        has_french_phone = is_french_number(lead.phone)  # Assure-toi que le champ s'appelle bien 'phone'
        has_email = bool(lead.email and lead.email.strip())

        assigned_user = accueil_users[counter % num_users]
        avg_quota = (TASKS_PER_DAY_MIN + TASKS_PER_DAY_MAX) // 2
        day_offset = counter // (num_users * avg_quota)
        due_date = now + timedelta(days=day_offset)

        # --- LOGGING DU MODE TEST ---
        if dry_run:
            logger.info(f"▶️ Lead #{lead.id} ({lead.first_name} {lead.last_name})")
            logger.info(f"   ↳ Statut   : Passera de '{lead.status.code if lead.status else 'Aucun'}' à 'ABSENT'")
            logger.info(f"   ↳ SMS      : {'✅ OUI' if has_french_phone else '❌ NON'} (Tel: {lead.phone})")
            logger.info(f"   ↳ Email    : {'✅ OUI' if has_email else '❌ NON'} (Email: {lead.email})")
            logger.info(f"   ↳ Tâche    : Assignée à {assigned_user.email} pour le {due_date.strftime('%d/%m/%Y')}\n")
            counter += 1
            continue

        # --- EXÉCUTION RÉELLE (Si dry_run=False) ---
        with transaction.atomic():
            # A. Mise à jour du statut
            if absent_status:
                lead.status = absent_status
                lead.save(update_fields=['status'])

            # B. Déclenchement Notification SMS (Uniquement FR)
            if has_french_phone:
                send_absent_urgency_sms_task.delay(lead.id)

            # C. Déclenchement Notification Email (Uniquement si Email présent)
            if has_email:
                pass
                # 👇 Décommente cette ligne et mets ta vraie tâche d'email !
                # send_absent_email_task.delay(lead.id)

            # D. Répartition intelligente des tâches
            if not LeadTask.objects.filter(lead=lead, task_type=task_type, completed_at__isnull=True).exists():
                LeadTask.objects.create(
                    lead=lead,
                    task_type=task_type,
                    status=LeadTaskStatus.TODO,
                    title=f"Relancer {lead.first_name or 'le lead'} (Absent RDV)",
                    description=f"Le RDV était prévu le {lead.appointment_date.strftime('%d/%m à %H:%M')}. Reprogrammer.",
                    due_at=due_date,
                    assigned_to=assigned_user,
                    metadata={"auto_distributed": True, "day_offset": day_offset}
                )

                # Log de l'événement
                LeadEvent.log(lead, "LEAD_MARKED_ABSENT_AUTO",
                              data={"assigned_to": assigned_user.id, "due_date": due_date.isoformat()})

        counter += 1

    logger.info("=" * 60)
    if dry_run:
        logger.info(f"✅ FIN DU TEST : {counter} leads auraient été traités.")
        logger.info("👉 Pour lancer en vrai, modifie le bas du fichier : run(dry_run=False)")
    else:
        logger.info(f"✅ FIN DU TRAITEMENT : {counter} leads mis à jour et notifiés.")


if __name__ == "__main__":
    # ⚠️ ICI ON EST EN MODE TEST.
    # Change à False quand tu as lu les logs et que tu es sûr de toi !
    run(dry_run=True)