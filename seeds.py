import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tds.settings.dev")
import django

django.setup()

import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import phonenumbers
from django.db import transaction
from django.utils import timezone
from faker import Faker
from phonenumbers import PhoneNumberFormat

from api.appointment.models import Appointment
from api.booking.models import SlotQuota
from api.clients.enums import (
    Civilite,
    SituationFamiliale,
    SituationProfessionnelle,
    SourceInformation,
    VisaType,
)
from api.clients.models import Client
from api.comments.models import Comment
from api.contracts.models import Contract
from api.documents.models import Document
from api.jurist_appointment.models import JuristAppointment
from api.jurist_availability_date.models import JuristGlobalAvailability
from api.lead_status.models import LeadStatus
from api.leads.models import Lead
from api.opening_hours.models import OpeningHours
from api.payments.enums import PaymentMode
from api.payments.models import PaymentReceipt
from api.services.models import Service
from api.special_closing_period.models import SpecialClosingPeriod
from api.statut_dossier.models import StatutDossier
from api.user_unavailability.models import UserUnavailability
from api.users.models import User
from api.users.roles import UserRoles
from api.utils.jurist_slots import get_slots_for_day

fake = Faker("fr_FR")


def generate_french_phone_number():
    prefix = random.choice(["06", "07"])
    suffix = "".join(str(random.randint(0, 9)) for _ in range(8))
    number = prefix + suffix
    phone_obj = phonenumbers.parse(number, "FR")
    return phonenumbers.format_number(phone_obj, PhoneNumberFormat.E164)


# --- Nettoyage complet ---
print("🧹 Suppression des données...")
Appointment.objects.all().delete()
JuristAppointment.objects.all().delete()
Comment.objects.all().delete()
PaymentReceipt.objects.all().delete()
Contract.objects.all().delete()
Document.objects.all().delete()
Client.objects.all().delete()
Lead.objects.all().delete()
User.objects.exclude(email="admin@example.com").delete()
Service.objects.all().delete()
LeadStatus.objects.all().delete()
StatutDossier.objects.all().delete()
OpeningHours.objects.all().delete()
SpecialClosingPeriod.objects.all().delete()
JuristGlobalAvailability.objects.all().delete()
SlotQuota.objects.all().delete()
UserUnavailability.objects.all().delete()  # <-- Ajouté pour remise à zéro

# --- CRENEAUX GLOBAUX JURISTES ---
print("📅 Création des créneaux globaux juriste...")

JURIST_GLOBAL_AVAILABILITIES = [
    {"day_of_week": 1, "start_time": time(10, 0), "end_time": time(13, 30)},  # Mardi
    {"day_of_week": 3, "start_time": time(14, 30), "end_time": time(18, 0)},  # Jeudi
]
for slot in JURIST_GLOBAL_AVAILABILITIES:
    obj, created = JuristGlobalAvailability.objects.get_or_create(
        day_of_week=slot["day_of_week"],
        start_time=slot["start_time"],
        end_time=slot["end_time"],
    )
    print(f"  {'✅' if created else '⚠️'} {obj}")
print("✅ Créneaux globaux juriste créés")

# --- HORAIRES D'OUVERTURE PAR DÉFAUT (LUNDI à DIMANCHE) ---
print("🕰️ Création des horaires d'ouverture (lundi à dimanche)...")
# day_of_week, open_time, close_time, slot_minutes, capacity, is_active
opening_hours_defaults = [
    (0, time(9, 0), time(18, 0), 30, 2, True),  # Lundi
    (1, time(9, 0), time(18, 0), 30, 2, True),  # Mardi
    (2, time(9, 0), time(18, 0), 30, 2, True),  # Mercredi
    (3, time(9, 0), time(18, 0), 30, 2, True),  # Jeudi
    (4, time(9, 0), time(18, 0), 30, 2, True),  # Vendredi
    (5, None, None, 30, 1, False),  # Samedi (fermé par défaut)
    (6, None, None, 30, 1, False),  # Dimanche (fermé par défaut)
]
for day, open_t, close_t, slot_min, capacity, active in opening_hours_defaults:
    obj, created = OpeningHours.objects.update_or_create(
        day_of_week=day,
        defaults={
            "open_time": open_t,
            "close_time": close_t,
            "slot_duration_minutes": slot_min,
            "capacity_per_slot": capacity,
            "is_active": active,
        },
    )
    print(f"  {'✅' if created else '♻️'} {obj}")
print("✅ Horaires créés/mis à jour (lundi-dimanche)")

# --- FERMETURES EXCEPTIONNELLES ---
print("🚫 Ajout de fermetures exceptionnelles...")
closing_periods = [
    {"label": "Noël", "start_date": date(2025, 12, 25), "end_date": date(2025, 12, 25)},
    {
        "label": "15 août",
        "start_date": date(2025, 8, 15),
        "end_date": date(2025, 8, 15),
    },
    {
        "label": "Vacances d'été",
        "start_date": date(2025, 8, 5),
        "end_date": date(2025, 8, 23),
    },
    {
        "label": "Travaux exceptionnels",
        "start_date": date(2025, 10, 3),
        "end_date": date(2025, 10, 7),
    },
]
for period in closing_periods:
    obj, created = SpecialClosingPeriod.objects.get_or_create(
        label=period["label"],
        start_date=period["start_date"],
        end_date=period["end_date"],
    )
    print(f"  {'✅' if created else '⚠️'} {obj}")
print("✅ Fermetures exceptionnelles créées")

# --- SERVICES ---
SERVICES_SEED = [
    {"code": "TITRE_SEJOUR", "label": "Titre de séjour", "price": Decimal("1590.00")},
    {
        "code": "REGROUPEMENT_FAMILIAL",
        "label": "Regroupement familial",
        "price": Decimal("1590.00"),
    },
    {"code": "NATURALISATION", "label": "Naturalisation", "price": Decimal("1290.00")},
    {"code": "RENOUVELLEMENT", "label": "Renouvellement", "price": Decimal("990.00")},
    {
        "code": "SUIVI_NATURALISATION",
        "label": "Suivi naturalisation",
        "price": Decimal("990.00"),
    },
    {"code": "DEMANDE_VISA", "label": "Demande de visa", "price": Decimal("990.00")},
    {"code": "DUPLICATA", "label": "Duplicata", "price": Decimal("990.00")},
    {"code": "SUIVI_DOSSIER", "label": "Suivi de dossier", "price": Decimal("690.00")},
    {"code": "DCEM", "label": "DCEM", "price": Decimal("590.00")},
    {"code": "PRISE_RDV", "label": "Prise de RDV", "price": Decimal("0.00")},
    {"code": "AUTRES", "label": "Autres", "price": Decimal("0.00")},
]
service_map = {}
for s in SERVICES_SEED:
    service, _ = Service.objects.get_or_create(code=s["code"], defaults=s)
    service_map[s["code"]] = service

# --- STATUTS LEAD ---
LEAD_STATUSES = [
    {"code": "RDV_CONFIRME", "label": "Rendez-vous confirmé", "color": "#60a5fa"},
    {"code": "RDV_PLANIFIE", "label": "Rendez-vous planifié", "color": "#818cf8"},
    {"code": "PRESENT", "label": "Présent", "color": "#34d399"},
    {"code": "ABSENT", "label": "Absent", "color": "#f87171"},
]
lead_status_map = {}
for s in LEAD_STATUSES:
    status, _ = LeadStatus.objects.get_or_create(code=s["code"], defaults=s)
    lead_status_map[s["code"]] = status

# --- STATUTS DOSSIER ---
DOSSIER_STATUSES = [
    {"code": "EN_ATTENTE", "label": "En attente", "color": "#cccccc"},
    {"code": "INCOMPLET", "label": "Incomplet", "color": "#fbbf24"},
    {"code": "COMPLET", "label": "Complet", "color": "#34d399"},
    {"code": "VALIDE", "label": "Validé", "color": "#4ade80"},
    {"code": "REFUSE", "label": "Refusé", "color": "#f87171"},
]
dossier_status_map = {}
for s in DOSSIER_STATUSES:
    status, _ = StatutDossier.objects.get_or_create(code=s["code"], defaults=s)
    dossier_status_map[s["code"]] = status

# --- Utilisateurs ---
print("👤 Création des utilisateurs...")
users_info = [
    ("admin@example.com", "Admin", "User", UserRoles.ADMIN),
    ("mtakoumba@gmail.com", "Admin", "User", UserRoles.ADMIN),
    ("accueil@example.com", "Accueil", "User", UserRoles.ACCUEIL),
    ("conseiller1@example.com", "Conseiller1", "User", UserRoles.CONSEILLER),
    ("conseiller2@example.com", "Conseiller2", "User", UserRoles.CONSEILLER),
    ("juriste1@example.com", "Juriste", "Dupont", UserRoles.JURISTE),
    ("juriste2@example.com", "Juriste", "Martin", UserRoles.JURISTE),
    ("juriste3@example.com", "Juriste", "Bernard", UserRoles.JURISTE),
]
user_map = {}
for email, first, last, role in users_info:
    user, _ = User.objects.update_or_create(
        email=email,
        defaults={
            "first_name": first,
            "last_name": last,
            "role": role,
            "is_active": True,
        },
    )
    user.set_password("Password@1")
    user.save()
    user_map[email] = user
    print(f"✅ {email} ({role})")

conseillers = [u for u in user_map.values() if u.role == UserRoles.CONSEILLER]
juristes = [u for u in user_map.values() if u.role == UserRoles.JURISTE]

# --- Indisponibilités utilisateurs ---
print("⛔ Ajout d’indisponibilités utilisateurs...")
total_unavails = 0
for user in user_map.values():
    for _ in range(random.randint(0, 2)):
        start = fake.date_between_dates(
            date_start=date.today() + timedelta(days=1),
            date_end=date.today() + timedelta(days=60),
        )
        if random.random() < 0.5:
            end = start
        else:
            end = start + timedelta(days=random.randint(1, 4))
        label = random.choice(
            [
                "Vacances",
                "Congé maladie",
                "Absence personnelle",
                "Formation",
                "Raison inconnue",
                "",
                "",
            ]
        )
        UserUnavailability.objects.create(
            user=user,
            start_date=start,
            end_date=end,
            label=label,
        )
        total_unavails += 1
print(f"✅ {total_unavails} indisponibilités ajoutées pour les utilisateurs")

# --- Leads avec multi-assignation conseiller et juriste ---
print("📞 Création des leads variés (multi-assignation)...")
leads = []
for i in range(10):
    status = random.choice(list(lead_status_map.values()))
    dossier_status = random.choice(list(dossier_status_map.values()))
    now = timezone.now()
    lead = Lead.objects.create(
        first_name=fake.first_name(),
        last_name=fake.last_name(),
        email=fake.email(),
        phone=generate_french_phone_number(),
        appointment_date=(
            now + timedelta(days=random.randint(0, 15))
            if "RDV" in status.code
            else None
        ),
        status=status,
        statut_dossier=dossier_status,
    )
    # Multi-assignation conseillers : entre 1 et 2 conseillers par lead
    num_conseillers = random.randint(1, 2)
    assigned_conseillers = random.sample(conseillers, k=num_conseillers)
    lead.assigned_to.set(assigned_conseillers)

    # Multi-assignation juristes : entre 0 et 2 juristes par lead (peut être 0 !)
    num_juristes = random.randint(0, 2)
    juristes_users = random.sample(juristes, k=num_juristes) if num_juristes > 0 else []
    lead.jurist_assigned.set(juristes_users)  # <-- IMPORTANT : champ ManyToManyField

    lead.save()
    leads.append(lead)
print(f"✅ {len(leads)} leads créés (multi-assignation conseiller/juriste)")

# --- Créneaux juristes ---
print("📆 Création des rendez-vous juriste (JuristAppointment)...")
all_slots = []
today = timezone.now().date()
for i in range(60):
    d = today + timedelta(days=i)
    all_slots.extend(
        get_slots_for_day(d)
    )  # get_slots_for_day DOIT utiliser les créneaux globaux ici
jurist_appointments = []
used_slots = set()
random.shuffle(all_slots)
for lead in leads:
    for juriste in lead.jurist_assigned.all():
        count = 0
        possible_slots = all_slots[:]
        random.shuffle(possible_slots)
        for slot in possible_slots:
            key = (juriste.id, slot)
            if key in used_slots:
                continue
            jurist_appointments.append(
                JuristAppointment(
                    lead=lead,
                    jurist=juriste,
                    date=slot,
                    created_by=random.choice(conseillers),
                )
            )
            used_slots.add(key)
            count += 1
            if count >= random.choice([0, 1, 2]):
                break
JuristAppointment.objects.bulk_create(jurist_appointments)
print(f"✅ {len(jurist_appointments)} jurist-appointments créés (2 mois glissants)")

# --- Appointments classiques (RDV Lead/Conseiller) ---
print("📅 Création des rendez-vous classiques (Appointment)...")
appointments = []
for lead in leads:
    nb_appointments = random.randint(1, 3)
    for i in range(nb_appointments):
        dt = timezone.make_aware(
            datetime(
                year=(
                    timezone.now().year
                    if timezone.now().month < 11
                    else timezone.now().year + 1
                ),
                month=random.choice(
                    [timezone.now().month, (timezone.now() + timedelta(days=30)).month]
                ),
                day=random.randint(1, 28),
                hour=random.randint(8, 18),
                minute=random.choice([0, 30]),
            )
        )
        if Appointment.objects.filter(lead=lead, date=dt).exists():
            continue
        if JuristAppointment.objects.filter(lead=lead, date=dt).exists():
            continue
        appointments.append(
            Appointment(
                lead=lead,
                date=dt,
                note=fake.sentence() if random.random() < 0.7 else "",
                created_by=random.choice(conseillers),
            )
        )
Appointment.objects.bulk_create(appointments)
print(f"✅ {len(appointments)} rendez-vous classiques créés")

# --- Clients et Documents ---
print("📁 Création des clients et documents...")
clients = []
for lead in leads:
    nb_enfants = random.randint(0, 3)
    type_demande_code = random.choice(list(service_map.keys()))

    # Champs ANEF
    has_anef = random.choice([True, False])
    anef_email = fake.unique.email() if has_anef else ""
    anef_password = (
        fake.password(
            length=14, special_chars=True, digits=True, upper_case=True, lower_case=True
        )
        if has_anef
        else ""
    )

    client = Client.objects.create(
        lead=lead,
        source=random.sample([s[0] for s in SourceInformation.choices], k=2),
        civilite=random.choice([c[0] for c in Civilite.choices]),
        date_naissance=fake.date_of_birth(minimum_age=18, maximum_age=60),
        lieu_naissance=fake.city(),
        pays=fake.country(),
        nationalite=fake.current_country(),
        adresse=fake.street_address(),
        code_postal=fake.postcode(),
        ville=fake.city(),
        date_entree_france=timezone.now().date()
        - timedelta(days=random.randint(1000, 4000)),
        a_un_visa=random.choice([True, False]),
        type_visa=random.choice([v[0] for v in VisaType.choices]),
        statut_refugie_ou_protection=random.choice([True, False]),
        type_demande=service_map[type_demande_code],
        demande_deja_formulee=random.choice([True, False]),
        demande_formulee_precise=fake.sentence() if random.random() < 0.3 else "",
        situation_familiale=random.choice([s[0] for s in SituationFamiliale.choices]),
        a_des_enfants=nb_enfants > 0,
        nombre_enfants=nb_enfants,
        nombre_enfants_francais=random.randint(0, nb_enfants),
        enfants_scolarises=random.choice([True, False]) if nb_enfants else False,
        naissance_enfants_details=fake.text(100) if nb_enfants else "",
        situation_pro=random.choice([p[0] for p in SituationProfessionnelle.choices]),
        domaine_activite=fake.job(),
        nombre_fiches_paie=random.randint(1, 6),
        a_deja_eu_oqtf=random.choice([True, False]),
        remarques=fake.sentence(),
        # --- Nouveaux champs ANEF ---
        has_anef_account=has_anef,
        anef_email=anef_email,
        anef_password=anef_password,
    )
    clients.append(client)
    doc_urls = [
        "https://www.africau.edu/images/default/sample.pdf",
        "https://file-examples.com/storage/fe73f36e226f5c4e8cb08a2/2017/10/file-example_PDF_1MB.pdf",
        "https://randomuser.me/api/portraits/men/32.jpg",
        "https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=600&h=800&auto=format",
    ]
    for url in random.sample(doc_urls, k=random.randint(1, 3)):
        Document.objects.create(client=client, url=url)
print(f"✅ {len(clients)} clients créés avec documents mock")

# --- Paiements & Contrats ---
print("💶 Génération des paiements...")
for client in clients:
    try:
        with transaction.atomic():
            service = client.type_demande
            base_price = (
                service.price
                if isinstance(service.price, Decimal)
                else Decimal(str(service.price))
            )
            remise = random.choice([0, 10, 20])
            discount = Decimal(remise)
            ratio_discount = (Decimal("100") - discount) / Decimal("100")
            real_amount_due = (base_price * ratio_discount).quantize(Decimal("0.01"))

            # Crée et SAUVEGARDE le contrat pour obtenir une PK immédiatement
            contract = Contract.objects.create(
                client=client,
                created_by=random.choice(conseillers),
                service=service,
                amount_due=base_price,
                discount_percent=discount,
            )

            # Générer des reçus de paiement
            total_receipts = random.choice([1, 2, 3])
            receipt_amount = (real_amount_due / total_receipts).quantize(
                Decimal("0.01")
            )
            total_paid = Decimal("0.00")
            today = timezone.now().date()

            for i in range(total_receipts):
                is_last = i == total_receipts - 1
                remaining = (real_amount_due - total_paid).quantize(Decimal("0.01"))
                actual_amount = remaining if is_last else min(receipt_amount, remaining)
                if actual_amount <= Decimal("0.00"):
                    break
                next_due = (
                    (today + timedelta(days=30 * (i + 1))) if not is_last else None
                )
                # Utilise contract_id pour éviter tout accès relationnel précoce
                PaymentReceipt.objects.create(
                    client=client,
                    contract_id=contract.id,
                    amount=actual_amount,
                    mode=random.choice([m[0] for m in PaymentMode.choices]),
                    payment_date=timezone.now(),
                    created_by=random.choice(conseillers),
                    next_due_date=next_due,
                )
                total_paid += actual_amount

            # --- Annulation aléatoire du contrat (10%) ---
            if random.random() < 0.1:
                contract.is_cancelled = True
                contract.save(update_fields=["is_cancelled"])

            # Si le contrat est annulé, mettre les remaining_amount à 0 pour tous les reçus
            if contract.is_cancelled:
                for receipt in contract.receipts.all():
                    receipt.remaining_amount = 0
                    receipt.save(update_fields=["remaining_amount"])

            # Remboursement optionnel (cohérent avec le total payé)
            refund_amount = Decimal("0.00")
            if total_paid > Decimal("0.00") and random.random() < 0.35:
                ratio_refund = Decimal(random.choice([10, 25, 50, 100])) / Decimal(
                    "100"
                )
                refund_amount = (total_paid * ratio_refund).quantize(Decimal("0.01"))
                if refund_amount > total_paid:
                    refund_amount = total_paid
                contract.refund_amount = refund_amount
                # Sauvegarde *après* la création des reçus
                contract.save(
                    update_fields=["refund_amount", "is_refunded"]
                )  # is_refunded mis à jour dans save()

            msg = f"Contrat {contract.id} créé avec {total_receipts} reçu(s) pour client {client.id}"
            if refund_amount > Decimal("0.00"):
                msg += f" — remboursement {refund_amount} €"
            print(f"✅ {msg}")
    except Exception as e:
        print(f"❌ Erreur pour client {client.id}: {e}")

print("✅ Paiements et reçus générés")

# --- Commentaires
print("💬 Création de commentaires...")
comments = []
for lead in leads:
    for _ in range(random.randint(0, 2)):
        comments.append(
            Comment(
                lead=lead,
                author=random.choice(conseillers),
                content=fake.paragraph(),
            )
        )
Comment.objects.bulk_create(comments)
print("✅ Commentaires ajoutés")