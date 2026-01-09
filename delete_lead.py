from django.utils import timezone
from api.leads.models import Lead

# Date du jour (timezone Django)
today = timezone.localdate()

# Queryset des leads créés aujourd'hui
qs = Lead.objects.filter(created_at__date=today)

count = qs.count()
print(f"🗑️ {count} lead(s) créé(s) aujourd’hui vont être supprimés")

# Suppression
qs.delete()

print("✅ Suppression terminée")