import os
import django
from django.db.models import Count, Q, Value, CharField
from django.db.models.functions import Lower, Coalesce

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tds.settings.prod")
django.setup()

from api.leads.models import Lead

print("=" * 60)
print("🔎 VÉRIFICATION DES DOUBLONS DANS LES LEADS")
print("=" * 60)

# ==============================
# 1️⃣ Identifier les doublons potentiels
# ==============================

duplicates = (
    Lead.objects
    .values(
        first_name_clean=Lower(Coalesce("first_name", Value("", output_field=CharField()))),
        last_name_clean=Lower(Coalesce("last_name", Value("", output_field=CharField()))),
        contact_clean=Coalesce(
            "phone",
            "email",
            output_field=CharField(),  # 👈 on force le type ici
        ),
    )
    .annotate(total=Count("id"))
    .filter(total__gt=1)
    .order_by("-total")
)

# ==============================
# 2️⃣ Résumé global
# ==============================

count_duplicates = duplicates.count()
if count_duplicates == 0:
    print("✅ Aucun doublon trouvé !")
else:
    print(f"⚠️  {count_duplicates} groupe(s) de doublons trouvé(s)\n")

# ==============================
# 3️⃣ Détails par groupe
# ==============================

for dup in duplicates[:20]:  # limite l'affichage aux 20 premiers groupes
    fn, ln, contact = dup["first_name_clean"], dup["last_name_clean"], dup["contact_clean"]
    print(f"➡️ {fn.title()} {ln.title()} ({contact}) — {dup['total']} occurrences")

    leads_group = Lead.objects.filter(
        Q(first_name__iexact=fn),
        Q(last_name__iexact=ln),
    ).filter(Q(phone=contact) | Q(email=contact)).order_by("created_at")

    for l in leads_group:
        print(f"   - #{l.id:04d} | {l.first_name} {l.last_name} | "
              f"{l.phone or l.email or '❌ aucun contact'} | créé le {l.created_at:%Y-%m-%d}")

    print("-" * 60)

# ==============================
# 4️⃣ Résumé final
# ==============================
if count_duplicates == 0:
    print("\n✅ Base de leads propre !")
else:
    print(f"\n📊 Total groupes doublons : {count_duplicates}")
    print("🧹 Pense à vérifier les leads affichés ci-dessus.")

print("=" * 60)