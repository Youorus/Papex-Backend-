import os
import django
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tds.settings.prod")
django.setup()

from django.db.models import Sum, Count, F, Value, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce, Greatest
from api.contracts.models import Contract
from api.payments.models import PaymentReceipt

print("=" * 60)
print("📊 VÉRIFICATION POST-NETTOYAGE")
print("=" * 60)

# Calculs
real_amount_due = ExpressionWrapper(
    F("amount_due") * (Value(1.0) - (Coalesce(F("discount_percent"), Value(Decimal("0.00"))) / Value(100.0))),
    output_field=DecimalField(max_digits=12, decimal_places=2),
)
amount_paid = Coalesce(Sum("receipts__amount"), Value(Decimal("0.00")))

contracts = Contract.objects.filter(is_cancelled=False).annotate(
    real_due=real_amount_due,
    total_paid=amount_paid
)

agg = contracts.aggregate(
    sum_due=Sum('real_due'),
    sum_paid=Sum('total_paid')
)

due = agg['sum_due'] or Decimal('0.00')
paid = agg['sum_paid'] or Decimal('0.00')
balance = due - paid

print(f"\n💰 Montant dû (réel)     : {due:>15,.2f} €")
print(f"💳 Montant reçu (net)    : {paid:>15,.2f} €")
print(f"📊 Solde restant         : {balance:>15,.2f} €")
print(f"📈 Taux de recouvrement  : {(paid/due*100):>14.1f} %")

# Vérifier s'il reste des doublons
duplicates = PaymentReceipt.objects.values(
    'contract_id', 'amount', 'payment_date', 'mode'
).annotate(count=Count('id')).filter(count__gt=1).count()

print(f"\n🔍 Doublons restants     : {duplicates}")

if duplicates == 0:
    print("✅ Base de données propre !")
else:
    print(f"⚠️  Il reste {duplicates} groupes à vérifier")

print("\n" + "=" * 60)