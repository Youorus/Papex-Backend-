import pytest
from unittest.mock import patch, MagicMock
from api.leads.models import Lead
from api.comments.models import Comment
from api.whatsapp.lead_service import create_lead_from_kemora
from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_A_CONFIRMER

@pytest.mark.django_db
class TestProfessionalLeadCreation:
    
    @pytest.fixture(autouse=True)
    def setup_status(self):
        LeadStatus.objects.get_or_create(code=RDV_A_CONFIRMER, label="RDV à confirmer")

    def test_create_lead_with_situation_summary(self):
        """Vérifie que la synthèse IA est bien enregistrée comme commentaire."""
        summary_text = "Client sans-papiers travaillant en CDI. Demande AES."
        
        result = create_lead_from_kemora(
            first_name="Jean",
            last_name="Test",
            phone="0611223344",
            email="jean@test.com",
            sender_phone="33611223344",
            appointment_date="2026-06-01T10:00:00+02:00",
            appointment_type="presentiel",
            situation_summary=summary_text
        )
        
        assert result["status"] == "created"
        lead = Lead.objects.get(id=result["lead_id"])
        
        # Vérifier que le commentaire a été créé
        comment = Comment.objects.filter(lead=lead).first()
        assert comment is not None
        assert summary_text in comment.content
        assert "Synthèse IA" in comment.content
        assert comment.author is None # Système

    def test_update_lead_with_new_summary(self):
        """Vérifie qu'une mise à jour de RDV ajoute aussi une nouvelle synthèse."""
        lead = Lead.objects.create(
            first_name="Marc",
            last_name="Existant",
            phone="33699887766",
            status=LeadStatus.objects.get(code=RDV_A_CONFIRMER)
        )
        
        new_summary = "Mise à jour : Le client a reçu une OQTF."
        
        result = create_lead_from_kemora(
            first_name="Marc",
            last_name="Existant",
            phone="0699887766",
            email=None,
            sender_phone="33699887766",
            appointment_date="2026-07-01T14:00:00+02:00",
            appointment_type="visio",
            situation_summary=new_summary
        )
        
        assert result["status"] == "updated"
        
        # Vérifier le nouveau commentaire
        comment = Comment.objects.filter(lead=lead, content__contains=new_summary).first()
        assert comment is not None
