import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from api.leads.models import Lead
from api.clients.models import Client
from api.comments.models import Comment
from api.websocket.signals.leads import on_lead_saved
from api.websocket.signals.clients import on_client_saved
from api.websocket.signals.comments import on_comment_saved

from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_PLANIFIE

@pytest.mark.django_db
class TestWebSocketSignals:
    @pytest.fixture(autouse=True)
    def setup_status(self):
        LeadStatus.objects.get_or_create(code=RDV_PLANIFIE, label="RDV Planifié")

    @patch("api.websocket.signals.base.get_channel_layer")
    def test_lead_signal_broadcasts_to_correct_groups(self, mock_get_channel_layer):
        mock_layer = MagicMock()
        mock_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = mock_layer
        
        # Créer un lead
        lead = Lead.objects.create(
            first_name="John",
            last_name="Doe",
            phone="0123456789"
        )
        
    @pytest.mark.django_db(transaction=True)
    def test_lead_saved_broadcast(self):
        with patch("api.websocket.signals.base.get_channel_layer") as mock_get_layer:
            mock_layer = MagicMock()
            mock_layer.group_send = AsyncMock()
            mock_get_layer.return_value = mock_layer
            
            lead = Lead.objects.create(
                first_name="Test",
                last_name="User",
                phone="123456"
            )
            
            # Vérifier que group_send a été appelé
            # On attend 2 appels (un pour chaque groupe)
            assert mock_layer.group_send.call_count >= 2

    @pytest.mark.django_db(transaction=True)
    def test_client_saved_broadcast(self):
        with patch("api.websocket.signals.base.get_channel_layer") as mock_get_layer:
            mock_layer = MagicMock()
            mock_layer.group_send = AsyncMock()
            mock_get_layer.return_value = mock_layer
            
            lead = Lead.objects.create(first_name="L", last_name="L", phone="1")
            client = Client.objects.create(lead=lead)
            
            assert mock_layer.group_send.call_count >= 2
