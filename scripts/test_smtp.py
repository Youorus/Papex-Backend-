from django.core.mail import send_mail
from django.conf import settings

print("🧪 TEST SMTP DJANGO\n")

print("EMAIL_BACKEND =", settings.EMAIL_BACKEND)
print("EMAIL_HOST =", getattr(settings, "EMAIL_HOST", None))
print("EMAIL_PORT =", getattr(settings, "EMAIL_PORT", None))
print("EMAIL_HOST_USER =", getattr(settings, "EMAIL_HOST_USER", None))
print("DEFAULT_FROM_EMAIL =", getattr(settings, "DEFAULT_FROM_EMAIL", None))
print()

try:
    send_mail(
        subject="🧪 Test SMTP Papex",
        message="Ceci est un email de test SMTP depuis Django.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=["mtakoumba@gmail.com"],  # ⬅️ mets TON email
        fail_silently=False,
    )
    print("✅ SMTP OK — email envoyé avec succès")

except Exception as e:
    print("❌ SMTP KO — erreur détectée")
    print(type(e).__name__, e)
    raise
