import os
import django
import sys
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'papex.settings')
django.setup()

from api.creators.models import CreatorProfile, PromoCode
from api.leads.models import Lead
from api.clients.models import Client
from api.contracts.models import Contract
from api.services.models import Service
from api.users.models import User
from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_PLANIFIE

def test_flow():
    print("--- DÉBUT DU TEST DU FLUX CRÉATEUR ---")
    
    # 1. Préparation (Service et Statut)
    service, _ = Service.objects.get_or_create(name="Service Test", defaults={'price': 1000})
    status, _ = LeadStatus.objects.get_or_create(code=RDV_PLANIFIE, defaults={'label': 'Planifié'})
    
    # 2. Création du Créateur
    user, created = User.objects.get_or_create(
        email="test_creator@papex.fr",
        defaults={'first_name': 'Jean', 'last_name': 'Creator', 'role': 'CREATOR'}
    )
    if created: user.set_password('password123'); user.save()
    
    creator, _ = CreatorProfile.objects.get_or_create(user=user)
    print(f"✅ Créateur créé : {creator}")
    
    # 3. Création du Code Promo (10% comm + 50€ bonus)
    promo, _ = PromoCode.objects.get_or_create(
        code="TEST2026",
        creator=creator,
        defaults={'commission_rate': 10.00, 'bonus_amount': 50.00}
    )
    print(f"✅ Code Promo créé : {promo.code} (10% + 50€ bonus)")
    
    # 4. Arrivée d'un Lead avec ce code
    lead = Lead.objects.create(
        first_name="Marc", last_name="Prospect", 
        phone="0600000000", status=status,
        creator_profile=creator, promo_code=promo
    )
    print(f"✅ Lead créé et lié au code {promo.code}")
    
    # 5. Conversion en Client et Contrat
    client = Client.objects.create(lead=lead)
    contract = Contract.objects.create(
        client=client, service=service, amount_due=1000.00, discount_percent=0.00
    )
    print(f"✅ Contrat de {contract.amount_due}€ créé pour le client")
    
    # 6. Vérification des KPIs (simulée via la logique de la vue)
    # Calcul attendu : 10% de 1000€ (100€) + 50€ bonus = 150€
    
    total_leads = creator.leads.count()
    contracts_queryset = Contract.objects.filter(client__lead__creator_profile=creator, is_cancelled=False)
    total_contracts = contracts_queryset.count()
    total_revenue = contracts_queryset.aggregate(s=django.db.models.Sum('amount_due'))['s'] or 0
    
    total_commissions = Decimal("0.00")
    for c in contracts_queryset:
        pc = c.client.lead.promo_code
        total_commissions += (c.real_amount * pc.commission_rate / Decimal("100.00")) + pc.bonus_amount
        
    print("\n--- RÉSULTATS DES STATS ---")
    print(f"Nombre de Leads : {total_leads} (Attendu: 1)")
    print(f"Nombre de Contrats : {total_contracts} (Attendu: 1)")
    print(f"Chiffre d'Affaire : {total_revenue}€ (Attendu: 1000€)")
    print(f"Commission Totale : {total_commissions}€ (Attendu: 150€)")
    
    if total_commissions == Decimal("150.00"):
        print("\n🏆 TEST RÉUSSI : La logique de calcul est parfaite !")
    else:
        print(f"\n❌ ÉCHEC : La commission calculée ({total_commissions}) ne correspond pas à l'attendu (150.00)")

if __name__ == "__main__":
    test_flow()
