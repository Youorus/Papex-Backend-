from api.leads.models import Lead
from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_CONFIRME

lead = Lead.objects.create(
    first_name="Test",
    last_name="AutoMail",
    email="mtakoumba@gmail.com",
    phone="0600000000",
    appointment_date="2026-01-15 14:30:00",
    status=LeadStatus.objects.get(code=RDV_CONFIRME),
)

print("Lead créé :", lead.id, lead.email)

# La notification est envoyée automatiquement via perform_create
# Ici on la déclenche manuellement pour simuler exactement le flux
from api.leads.views import LeadViewSet
LeadViewSet()._send_notifications(lead)

print("Notification déclenchée")
