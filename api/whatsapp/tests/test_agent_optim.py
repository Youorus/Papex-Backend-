import pytest
from unittest.mock import patch, MagicMock
from django.core.cache import cache
from api.whatsapp.views import _schedule_debounced_agent
from api.whatsapp.agent.handler import trigger_agent_response

@pytest.mark.django_db
class TestAgentOptimization:
    
    @patch("api.whatsapp.views._dispatch_agent_q2")
    def test_debounce_logic_updates_token(self, mock_dispatch):
        """Vérifie que chaque nouvel appel écrase le token précédent dans le cache."""
        phone = "33612345678"
        
        # 1er message
        _schedule_debounced_agent("Hello", phone, None, "wa1")
        token1 = cache.get(f"kemora_debounce_{phone}")
        assert token1 is not None
        
        # 2ème message (burst)
        _schedule_debounced_agent("World", phone, None, "wa2")
        token2 = cache.get(f"kemora_debounce_{phone}")
        
        assert token2 != token1
        assert mock_dispatch.call_count == 2

    @patch("api.whatsapp.agent.handler.generate_agent_reply")
    @patch("api.whatsapp.agent.handler.send_whatsapp_message")
    @patch("api.whatsapp.agent.handler.send_whatsapp_typing_indicator")
    @patch("time.sleep", return_value=None) # On ne veut pas attendre réellement pendant le test
    def test_typing_delay_simulation(self, mock_sleep, mock_typing, mock_send, mock_gen):
        """Vérifie que la simulation de frappe est déclenchée."""
        mock_gen.return_value = ("Ceci est une réponse assez longue pour déclencher un délai de frappe significatif.", {})
        mock_send.return_value = {"messages": [{"id": "out123"}]}
        
        trigger_agent_response(
            incoming_body="Test",
            sender_phone="33612345678",
            lead_id=None,
            wa_message_id="in123",
            debounce_token="" # Pas de debounce pour ce test unitaire
        )
        
        # Vérifie que le typing indicator a été appelé au moins une fois
        assert mock_typing.called
        # Vérifie que sleep a été appelé (simulation de délai)
        assert mock_sleep.called
        # Vérifie que l'envoi final a eu lieu
        assert mock_send.called
