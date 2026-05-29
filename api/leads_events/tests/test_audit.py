import pytest
from django.contrib.auth import get_user_model
from api.leads.models import Lead
from api.comments.models import Comment
from api.leads_events.models import LeadEvent
from api.utils.context import set_current_user
from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_PLANIFIE

User = get_user_model()

@pytest.mark.django_db(transaction=True)
class TestAuditTrail:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        LeadStatus.objects.get_or_create(code=RDV_PLANIFIE, label="RDV Planifié")
        self.user = User.objects.create_user(email="audit@test.com", password="password", first_name="Audit", last_name="User")
        set_current_user(self.user)

    def test_lead_creation_audit(self):
        lead = Lead.objects.create(first_name="Audit", last_name="Lead", phone="000")
        
        # Vérifier qu'un événement LEAD_CREATED a été créé
        event = LeadEvent.objects.filter(lead=lead, event_type__code="LEAD_CREATED").first()
        assert event is not None
        assert event.actor == self.user

    def test_lead_update_audit_with_diff(self):
        lead = Lead.objects.create(first_name="Initial", last_name="Lead", phone="111")
        
        # Modifier le lead
        lead.first_name = "Updated"
        lead.save()
        
        # Vérifier qu'un événement LEAD_UPDATED a été créé avec le diff
        event = LeadEvent.objects.filter(lead=lead, event_type__code="LEAD_UPDATED").first()
        assert event is not None
        assert "diff" in event.data
        assert event.data["diff"]["first_name"]["old"] == "Initial"
        assert event.data["diff"]["first_name"]["new"] == "Updated"

    def test_comment_audit(self):
        lead = Lead.objects.create(first_name="Comment", last_name="Test", phone="222")
        Comment.objects.create(lead=lead, author=self.user, content="Test comment")
        
        # Vérifier qu'un événement COMMENT_ADDED a été créé pour ce lead
        event = LeadEvent.objects.filter(lead=lead, event_type__code="COMMENT_ADDED").first()
        assert event is not None
        # Pour une création, data peut être vide ou ne pas contenir 'diff'
        assert "diff" not in event.data or event.data["diff"] == {}

    def test_event_with_attachments(self):
        from api.documents.models import Document
        from api.clients.models import Client
        
        lead = Lead.objects.create(first_name="Attachment", last_name="Test", phone="333")
        client, _ = Client.objects.get_or_create(lead=lead)
        
        doc = Document.objects.create(client=client, url="https://example.com/test.pdf")
        
        event = LeadEvent.log(
            lead=lead,
            event_code="DOCUMENT_UPLOADED",
            actor=self.user,
            attachment_ids=[doc.id]
        )
        
        assert event.attachments.count() == 1
        assert doc in event.attachments.all()

    def test_update_event_attachments_via_serializer(self):
        from api.leads_events.serializers import LeadEventSerializer
        from api.documents.models import Document
        from api.clients.models import Client
        
        lead = Lead.objects.create(first_name="Update", last_name="Attach", phone="444")
        client, _ = Client.objects.get_or_create(lead=lead)
        doc = Document.objects.create(client=client, url="https://example.com/update.pdf")
        
        event = LeadEvent.log(lead=lead, event_code="TEST_UPDATE")
        
        serializer = LeadEventSerializer(instance=event, data={"attachment_ids": [doc.id]}, partial=True)
        assert serializer.is_valid()
        serializer.save()
        
        event.refresh_from_db()
        assert event.attachments.count() == 1
        assert doc in event.attachments.all()
