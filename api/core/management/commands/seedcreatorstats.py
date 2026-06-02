from django.core.management.base import BaseCommand
import random
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_seed import Seed
from api.clients.models import Client
from api.contracts.models import Contract
from api.creators.models import CreatorProfile, PromoCode
from api.leads.models import Lead
from api.leads_events.models import LeadEvent
from api.payments.models import PaymentReceipt

User = get_user_model()

from api.services.models import Service

User = get_user_model()

class Command(BaseCommand):
    help = "Crée des données de test pour les statistiques d'un créateur."

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email du créateur pour qui générer les données.')

    def handle(self, *args, **options):
        creator_email = options['email']

        # --- Récupérer un service valide ---
        service = Service.objects.first()
        if not service:
            self.stdout.write(self.style.ERROR("ERREUR : Aucun service trouvé dans la base de données. Veuillez en créer un."))
            return

        try:
            creator_user = User.objects.get(email=creator_email)
            creator_profile = creator_user.creator_profile
        except (User.DoesNotExist, CreatorProfile.DoesNotExist):
            self.stdout.write(self.style.ERROR(f"ERREUR : Créateur avec l'email {creator_email} introuvable."))
            return

        self.stdout.write(f"Génération de données pour le créateur : {creator_profile.user.get_full_name()}...")

        promo_code, _ = PromoCode.objects.get_or_create(
            creator=creator_profile,
            code=f"TESTPROMO-{creator_profile.user.first_name.upper()}",
            defaults={
                "commission_rate": Decimal("15.00"),
                "bonus_amount": Decimal("5.00"),
                "status": PromoCode.Status.ACTIVE,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"- Code promo '{promo_code.code}' assuré."))

        # test_lead_ids = list(Lead.objects.filter(email__startswith="lead-test-").values_list('id', flat=True))
        # if test_lead_ids:
        #     LeadEvent.objects.filter(lead_id__in=test_lead_ids).delete()
        #     Client.objects.filter(lead_id__in=test_lead_ids).delete()
        #     Lead.objects.filter(id__in=test_lead_ids).delete()
        # self.stdout.write("- Anciennes données de test (non nettoyées).")

        seeder = Seed.seeder()

        for i in range(10):
            now = timezone.now()
            lead_email = f"lead-test-{i}-{now.strftime('%Y%m%d%H%M%S')}@example.com"
            first_name = seeder.faker.first_name()
            last_name = seeder.faker.last_name()

            lead = Lead.objects.create(
                first_name=first_name,
                last_name=last_name,
                email=lead_email,
                phone=seeder.faker.phone_number(),
                creator_profile=creator_profile,
                promo_code=promo_code,
                created_at=now - timedelta(days=random.randint(1, 30)),
            )

            client, _ = Client.objects.get_or_create(
                lead=lead,
                defaults={
                    "civilite": "M",
                },
            )

            if i < 5:
                contract = Contract.objects.create(
                    client=client,
                    service=service,
                    amount_due=Decimal(random.choice([100, 150, 200])),
                    is_signed=True,
                    created_at=lead.created_at + timedelta(hours=random.randint(1, 24)),
                )

                PaymentReceipt.objects.create(
                    client=client,
                    contract=contract,
                    amount=contract.amount_due,
                    mode="stripe",
                )
                self.stdout.write(f"  - Lead, Client, Contrat et Paiement créés pour {lead_email}")
            else:
                self.stdout.write(f"  - Lead et Client créés pour {lead_email}")

        self.stdout.write(self.style.SUCCESS("\\n-----------------------------------------"))
        self.stdout.write(self.style.SUCCESS("TERMINE : Les données de test ont été générées avec succès."))
        self.stdout.write(self.style.SUCCESS("Vous pouvez maintenant vérifier les KPIs pour ce créateur."))
        self.stdout.write(self.style.SUCCESS(f"URL de l'API : /api/creators/{creator_profile.id}/kpis/"))
        self.stdout.write(self.style.SUCCESS("-----------------------------------------"))
