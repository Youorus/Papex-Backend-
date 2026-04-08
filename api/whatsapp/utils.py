# api/whatsapp/utils.py
from api.leads.models import Lead

def get_lead_by_phone(wa_phone):
    """
    Meta envoie '33612345678'.
    On cherche dans Lead.phone en ignorant les préfixes.
    """
    # On prend les 9 derniers chiffres (standard mobile FR)
    clean_phone = wa_phone[-9:]
    return Lead.objects.filter(phone__icontains=clean_phone).first()