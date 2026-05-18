import os
import django
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from api.services.models import Service
from api.services.utils import code_from_label


SERVICES = [
    ("Changement de statut", "990.00"),
    ("Autorisation de travail", "990.00"),
]

def run():
    created_count = 0
    updated_count = 0

    for label, price in SERVICES:
        code = code_from_label(label)

        service, created = Service.objects.update_or_create(
            code=code,
            defaults={
                "label": label,
                "price": Decimal(price),
            },
        )

        if created:
            created_count += 1
            print(f"✅ Créé : {service.label} ({service.price} €)")
        else:
            updated_count += 1
            print(f"🔄 Mis à jour : {service.label} ({service.price} €)")

    print("----------")
    print(f"✅ Créés : {created_count}")
    print(f"🔄 Mis à jour : {updated_count}")
    print(f"📦 Total : {Service.objects.count()}")


if __name__ == "__main__":
    run()