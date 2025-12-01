import os
import django
from decimal import Decimal
import csv
from datetime import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tds.settings.prod")
django.setup()

from django.db.models import Sum, F, Value, DecimalField, ExpressionWrapper, Q
from django.db.models.functions import Coalesce
from api.contracts.models import Contract
from api.payments.models import PaymentReceipt

print("=" * 80)
print("📊 EXPORT CSV - CONTRATS ET PAIEMENTS")
print("=" * 80)

# Nom du fichier CSV
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
filename = f"contrats_paiements_analyse_{timestamp}.csv"

print(f"\n📝 Création du fichier : {filename}\n")

# Ouvrir le fichier CSV
with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
    writer = csv.writer(csvfile, delimiter=';')

    # En-têtes
    writer.writerow([
        'ID Contrat',
        'Client',
        'Email',
        'Téléphone',
        'Service',
        'Date Contrat',
        'Montant Dû',
        'Remise (%)',
        'Montant Dû Réel',
        'Nb Paiements',
        'Total Payé',
        'Solde Restant',
        '% Payé',
        'Statut',
        '--- DÉTAIL PAIEMENTS ---',
        'ID Reçu',
        'Date Paiement',
        'Montant',
        'Mode'
    ])

    # Totaux généraux
    total_contracts = 0
    total_due = Decimal('0.00')
    total_real_due = Decimal('0.00')
    total_paid = Decimal('0.00')
    total_balance = Decimal('0.00')
    total_payments = 0

    # Récupérer tous les contrats actifs
    contracts = Contract.objects.filter(
        is_cancelled=False
    ).select_related(
        'client__lead', 'service'
    ).prefetch_related(
        'receipts'
    ).order_by('-created_at')

    print(f"🔄 Traitement de {contracts.count()} contrats...\n")

    for contract in contracts:
        total_contracts += 1

        # Infos client
        client_name = f"{contract.client.lead.first_name or ''} {contract.client.lead.last_name or ''}".strip()
        client_email = contract.client.lead.email or ''
        client_phone = contract.client.lead.phone or ''

        # Infos service
        service_name = f"{contract.service.code} - {contract.service.label}" if contract.service else 'N/A'

        # Calculs financiers
        amount_due = contract.amount_due
        discount = contract.discount_percent or Decimal('0.00')
        real_due = amount_due * (Decimal('1.0') - discount / Decimal('100.0'))

        # Paiements
        payments = contract.receipts.all().order_by('payment_date', 'id')
        nb_payments = payments.count()
        total_paid_contract = sum(p.amount for p in payments)
        balance = real_due - total_paid_contract
        percent_paid = (total_paid_contract / real_due * 100) if real_due > 0 else 0

        # Statut
        if balance <= Decimal('1.00'):
            statut = '✅ SOLDÉ'
        elif total_paid_contract == 0:
            statut = '❌ NON PAYÉ'
        elif total_paid_contract < real_due:
            statut = '⏳ EN COURS'
        else:
            statut = '⚠️ SURPAYÉ'

        # Mise à jour des totaux
        total_due += amount_due
        total_real_due += real_due
        total_paid += total_paid_contract
        total_balance += balance
        total_payments += nb_payments

        # Ligne principale du contrat
        if nb_payments > 0:
            # Premier paiement sur la même ligne
            first_payment = payments[0]
            writer.writerow([
                contract.id,
                client_name,
                client_email,
                client_phone,
                service_name,
                contract.created_at.strftime('%d/%m/%Y'),
                f"{float(amount_due):.2f}",
                f"{float(discount):.2f}",
                f"{float(real_due):.2f}",
                nb_payments,
                f"{float(total_paid_contract):.2f}",
                f"{float(balance):.2f}",
                f"{float(percent_paid):.1f}",
                statut,
                '',
                first_payment.id,
                first_payment.payment_date.strftime('%d/%m/%Y'),
                f"{float(first_payment.amount):.2f}",
                first_payment.mode or 'N/A'
            ])

            # Paiements suivants sur des lignes séparées
            for payment in payments[1:]:
                writer.writerow([
                    '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',
                    payment.id,
                    payment.payment_date.strftime('%d/%m/%Y'),
                    f"{float(payment.amount):.2f}",
                    payment.mode or 'N/A'
                ])
        else:
            # Contrat sans paiement
            writer.writerow([
                contract.id,
                client_name,
                client_email,
                client_phone,
                service_name,
                contract.created_at.strftime('%d/%m/%Y'),
                f"{float(amount_due):.2f}",
                f"{float(discount):.2f}",
                f"{float(real_due):.2f}",
                0,
                '0.00',
                f"{float(real_due):.2f}",
                '0.0',
                statut,
                '',
                '', '', '', ''
            ])

        # Ligne de séparation visuelle
        writer.writerow([''] * 19)

        # Afficher la progression
        if total_contracts % 50 == 0:
            print(f"   ✓ {total_contracts} contrats traités...")

    # Lignes de totaux
    writer.writerow([''] * 19)
    writer.writerow([''] * 19)
    writer.writerow([
        '═══════════════',
        'TOTAUX GÉNÉRAUX',
        '═══════════════',
        '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''
    ])
    writer.writerow([''] * 19)
    writer.writerow([
        'Total Contrats :',
        total_contracts,
        '', '', '', '',
        'Total Dû :',
        f"{float(total_due):.2f} €",
        '',
        'Montant Dû Réel :',
        f"{float(total_real_due):.2f} €",
        '', '', '', '', '', '', '', ''
    ])
    writer.writerow([
        'Total Paiements :',
        total_payments,
        '', '', '', '',
        'Total Payé :',
        f"{float(total_paid):.2f} €",
        '',
        'Solde Restant :',
        f"{float(total_balance):.2f} €",
        '', '', '', '', '', '', '', ''
    ])
    writer.writerow([
        'Taux de recouvrement :',
        f"{(total_paid / total_real_due * 100):.2f} %" if total_real_due > 0 else '0%',
        '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''
    ])

print("\n" + "=" * 80)
print("✅ EXPORT TERMINÉ !")
print("=" * 80)
print(f"\n📄 Fichier créé : {filename}")
print(f"\n📊 RÉSUMÉ :")
print(f"   • Contrats exportés      : {total_contracts}")
print(f"   • Paiements exportés     : {total_payments}")
print(f"   • Montant dû (réel)      : {total_real_due:,.2f} €")
print(f"   • Total payé             : {total_paid:,.2f} €")
print(f"   • Solde restant          : {total_balance:,.2f} €")
print(f"   • Taux de recouvrement   : {(total_paid / total_real_due * 100):.1f} %")

# Statistiques supplémentaires
print(f"\n📈 STATISTIQUES :")

contracts_paid = Contract.objects.filter(
    is_cancelled=False
).annotate(
    total_paid=Coalesce(Sum('receipts__amount'), Value(Decimal('0.00')))
).filter(total_paid__gt=Decimal('0.00')).count()

contracts_unpaid = total_contracts - contracts_paid

contracts_fully_paid = Contract.objects.filter(
    is_cancelled=False
).annotate(
    real_due=ExpressionWrapper(
        F('amount_due') * (Value(1.0) - (Coalesce(F('discount_percent'), Value(Decimal('0.00'))) / Value(100.0))),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    ),
    total_paid=Coalesce(Sum('receipts__amount'), Value(Decimal('0.00')))
).filter(total_paid__gte=F('real_due') - Decimal('1.00')).count()

print(f"   • Contrats soldés        : {contracts_fully_paid} ({contracts_fully_paid / total_contracts * 100:.1f}%)")
print(f"   • Contrats en cours      : {contracts_paid - contracts_fully_paid}")
print(f"   • Contrats non payés     : {contracts_unpaid}")

print(f"\n💡 Ouvrez le fichier dans Excel/LibreOffice pour l'analyser !")
print("=" * 80)