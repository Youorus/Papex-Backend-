#!/usr/bin/env python3
"""
Script pour créer manuellement des leads, clients, contrats et paiements
"""
import os
import sys
import django
from decimal import Decimal
from datetime import datetime

# ⚙️ Configuration Django
DJANGO_SETTINGS_MODULE = 'tds.settings.prod'  # 👈 Modifiez selon votre configuration
os.environ.setdefault("DJANGO_SETTINGS_MODULE", DJANGO_SETTINGS_MODULE)
django.setup()

from api.leads.models import Lead
from api.clients.models import Client
from api.contracts.models import Contract
from api.payments.models import PaymentReceipt
from api.services.models import Service
from api.lead_status.models import LeadStatus


def normalize_phone(phone: str) -> str:
    """Normalise un numéro de téléphone"""
    import re
    if not phone:
        return ""
    phone = re.sub(r'\D', '', str(phone))
    if phone.startswith('33'):
        return phone
    if phone.startswith('0'):
        return '33' + phone[1:]
    return '33' + phone


def get_or_create_service(service_name: str, price: Decimal) -> Service:
    """Récupère ou crée un service"""
    from api.services.utils import code_from_label

    code = code_from_label(service_name)
    service, created = Service.objects.get_or_create(
        code=code,
        defaults={
            'label': service_name,
            'price': price
        }
    )

    if created:
        print(f"  ✅ Service créé: {service_name} ({price}€)")
    else:
        print(f"  ℹ️ Service existant: {service_name}")

    return service


def get_default_lead_status() -> LeadStatus:
    """Récupère le statut par défaut pour un lead"""
    try:
        # Essayer de récupérer "RDV_PLANIFIE" ou le premier statut disponible
        status = LeadStatus.objects.filter(code='RDV_PLANIFIE').first()
        if not status:
            status = LeadStatus.objects.first()
        return status
    except:
        print("⚠️ Aucun LeadStatus trouvé dans la DB")
        return None


def create_lead_client_contract(
        first_name: str,
        last_name: str,
        phone: str,
        email: str,
        service_name: str = None,
        service_id: int = None,
        amount_due: Decimal = None,
        payment_amount: Decimal = None,
        payment_mode: str = "ESPECES",
        contract_date: datetime = None,
        payment_date: datetime = None,
        is_cancelled: bool = False,
        contract_url: str = None
):
    """
    Crée un lead, client, contrat et paiement

    Args:
        first_name: Prénom
        last_name: Nom
        phone: Téléphone (sera normalisé)
        email: Email (peut être vide)
        service_name: Nom du service (ex: "Renouvellement Titre de séjour")
        service_id: ID du service existant (prioritaire sur service_name)
        amount_due: Montant du contrat
        payment_amount: Montant du paiement (si None, utilise amount_due)
        payment_mode: Mode de paiement (ESPECES, CARTE, VIREMENT, CHEQUE)
        contract_date: Date du contrat (si None, utilise date actuelle)
        payment_date: Date du paiement (si None, utilise date actuelle)
        is_cancelled: True si le contrat est annulé
        contract_url: URL du contrat PDF (si None, génère une URL factice)
    """

    print(f"\n{'=' * 80}")
    print(f"🔨 Création: {first_name} {last_name}")
    print(f"{'=' * 80}")

    # Normaliser le téléphone
    phone_normalized = normalize_phone(phone)

    # Dates par défaut
    if contract_date is None:
        contract_date = datetime.now()
    if payment_date is None:
        payment_date = datetime.now()
    if payment_amount is None:
        payment_amount = amount_due

    # URL de contrat factice si non fournie
    if contract_url is None:
        timestamp = int(contract_date.timestamp())
        contract_url = f"https://storage.example.com/contracts/contract_{timestamp}_{phone_normalized}.pdf"

    try:
        # 1. Vérifier si le lead existe déjà
        existing_lead = Lead.objects.filter(phone=phone_normalized).first()
        if existing_lead:
            print(f"⚠️ Lead existant trouvé pour {phone_normalized}")
            lead = existing_lead
        else:
            # Créer le Lead
            lead_status = get_default_lead_status()
            lead = Lead.objects.create(
                first_name=first_name,
                last_name=last_name,
                phone=phone_normalized,
                email=email or None,
                status=lead_status,
                created_at=contract_date
            )
            print(f"✅ Lead créé: {lead}")

        # 2. Créer le Client
        client, created = Client.objects.get_or_create(
            lead=lead,
            defaults={'created_at': contract_date}
        )

        if created:
            print(f"✅ Client créé")
        else:
            print(f"ℹ️ Client existant")

        # 3. Récupérer ou créer le Service
        if service_id:
            # Utiliser l'ID du service fourni
            try:
                service = Service.objects.get(id=service_id)
                print(f"✅ Service existant utilisé (ID: {service_id}): {service.label}")
                # Si amount_due n'est pas fourni, utiliser le prix du service
                if amount_due is None:
                    amount_due = service.price
            except Service.DoesNotExist:
                print(f"❌ Service avec ID {service_id} introuvable")
                return None
        elif service_name:
            # Créer ou récupérer le service par nom
            if amount_due is None:
                print(f"❌ amount_due requis si service créé par nom")
                return None
            service = get_or_create_service(service_name, amount_due)
        else:
            print(f"❌ service_name ou service_id requis")
            return None

        # 4. Créer le Contract
        contract = Contract.objects.create(
            client=client,
            service=service,
            amount_due=amount_due,
            discount_percent=Decimal('0.00'),
            created_at=contract_date,
            is_signed=True,
            is_cancelled=is_cancelled,
            contract_url=contract_url
        )

        cancelled_text = " (ANNULÉ)" if is_cancelled else ""
        print(f"✅ Contrat créé: {contract.id} - {amount_due}€{cancelled_text}")
        print(f"   URL: {contract_url}")

        # 5. Créer le PaymentReceipt
        payment = PaymentReceipt.objects.create(
            client=client,
            contract=contract,
            amount=payment_amount,
            mode=payment_mode,
            payment_date=payment_date
        )
        print(f"✅ Paiement créé: {payment_amount}€ ({payment_mode})")

        print(f"✅ ✅ ✅ Création terminée avec succès!")
        return lead, client, contract, payment

    except Exception as e:
        print(f"❌ Erreur lors de la création: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Fonction principale - Définissez vos données ici"""

    print("\n" + "=" * 80)
    print("🚀 CRÉATION MANUELLE DE CONTRATS")
    print("=" * 80 + "\n")

    # ========================================================================
    # 👇 DÉFINISSEZ VOS DONNÉES ICI
    # ========================================================================

    # Exemple 1: Utiliser un service existant par ID
    """
    create_lead_client_contract(
        first_name="Alida",
        last_name="Maliko",
        phone="767284065",
        email="",
        service_id=5,  # 👈 ID du service dans votre DB
        amount_due=Decimal("890.00"),
        payment_amount=Decimal("890.00"),
        payment_mode="ESPECES",
        contract_date=datetime(2025, 1, 13),
        payment_date=datetime(2025, 1, 13),
        is_cancelled=True  # 👈 False = actif, True = annulé
    )
    """

    # Exemple 2: Créer un nouveau service par nom
    create_lead_client_contract(
        first_name="AKAKPO ( MAMAN)",
        last_name="Akakpo",
        phone="33605670669",
        email="sergileakue@yahoo.fr",
        service_name="Inconnu",  # 👈 Nom du service
        amount_due=Decimal("1190.00"),
        payment_amount=Decimal("300.00"),
        payment_mode="CB",
        contract_date=datetime(2024, 11, 19),
        payment_date=datetime(2025, 1, 20),
        is_cancelled=True
    )

    """
    # Exemple 3: Contrat annulé
    create_lead_client_contract(
        first_name="Kadiatou",
        last_name="KANE",
        phone="753453048",
        email="",
        service_id=3,
        amount_due=Decimal("490.00"),
        payment_amount=Decimal("200.00"),
        payment_mode="ESPECES",
        contract_date=datetime(2025, 1, 20),
        payment_date=datetime(2025, 1, 20),
        is_cancelled=True  # 👈 Contrat annulé
    )
    """
    # ========================================================================
    # 👆 AJOUTEZ VOS AUTRES CONTRATS ICI
    # ========================================================================

    # Décommentez et modifiez selon vos besoins:
    """
    # Méthode 1: Avec service_id (recommandé)
    create_lead_client_contract(
        first_name="Prénom",
        last_name="Nom",
        phone="0612345678",
        email="email@example.com",
        service_id=5,  # ID du service dans la DB
        amount_due=Decimal("890.00"),
        payment_amount=Decimal("450.00"),
        payment_mode="ESPECES",
        contract_date=datetime(2025, 1, 15),
        payment_date=datetime(2025, 1, 15),
        is_cancelled=False
    )

    # Méthode 2: Avec service_name (crée le service si nécessaire)
    create_lead_client_contract(
        first_name="Prénom",
        last_name="Nom",
        phone="0612345678",
        email="email@example.com",
        service_name="Nom du service",
        amount_due=Decimal("890.00"),
        payment_amount=Decimal("450.00"),
        payment_mode="ESPECES",
        contract_date=datetime(2025, 1, 15),
        payment_date=datetime(2025, 1, 15),
        is_cancelled=False
    )
    """

    print("\n" + "=" * 80)
    print("✅ TOUS LES CONTRATS ONT ÉTÉ CRÉÉS")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()