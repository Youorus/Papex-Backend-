import os
import django

# Charger Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tds.settings.dev")  # adapte si besoin
django.setup()

from django.core.mail import send_mail

result = send_mail(
    subject="Test SMTP - TDS",
    message="Ceci est un test SMTP depuis ton script Python.",
    from_email="jennifer@titresdesejour.fr",
    recipient_list=["mtakoumba@gmail.com"],  # mets ton email perso
)

print("Résultat :", result)