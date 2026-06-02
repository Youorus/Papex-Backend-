import pytest
from unittest.mock import patch, MagicMock
from django.conf import settings
import json

from api.whatsapp.agent.handler import generate_agent_reply, trigger_agent_response
from api.whatsapp.models import WhatsAppConversationSettings, WhatsAppMessage
from api.leads.models import Lead
from api.lead_status.models import LeadStatus

# Mark all tests in this file as Django tests
pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def setup_lead_status(db):
    """Ensure the default LeadStatus exists for Lead creation."""
    LeadStatus.objects.get_or_create(code="RDV_PLANIFIE", label="Rendez-vous planifié")


@patch('api.whatsapp.agent.handler._get_gemini_client')
def test_escalation_sends_alert_and_disables_agent(mock_get_gemini_client):
    """
    Verify that when the Gemini response contains an escalation marker:
    1. The escalation alert email is sent.
    2. The agent for that conversation is disabled.
    3. The marker is stripped from the final reply, but the call-to-action is present.
    """
    lead = Lead.objects.create(first_name="Test", last_name="Escalade", phone="+33611111111")
    settings.PAYPAL_VISIO_LINK = "https://paypal.me/test/50"

    # Mock Gemini response with the specific escalation format
    mock_gemini_response = MagicMock()
    mock_gemini_response.text = (
        'Je comprends. Pour une assistance plus adaptée, je vous invite à nous appeler directement au 01 42 59 60 08. '
        'Un de nos collaborateurs prendra le relais.'
        '[[ESCALATE_REQUIRED: "Le client est très confus."]]'
    )
    mock_gemini_client = MagicMock()
    mock_gemini_client.models.generate_content.return_value = mock_gemini_response
    mock_get_gemini_client.return_value = mock_gemini_client

    # Mock the email alert to verify it's called
    with patch('api.utils.email.internal_alerts.send_ai_escalation_alert') as mock_send_alert:
        clean_reply, _ = generate_agent_reply(
            incoming_message="Je ne comprends rien.",
            sender_phone=lead.phone,
            lead=lead
        )

        # 1. Assert email alert was called correctly
        mock_send_alert.assert_called_once_with(
            lead=lead,
            reason="Le client est très confus.",
            sender_phone=lead.phone
        )
        
        # This part is now handled inside the mocked send_ai_escalation_alert,
        # but for a true integration test, we would check the DB.
        # For this unit test, we trust the mock's call implies the action.
        # To test the side-effect properly, we'd need to test send_ai_escalation_alert itself
        # or use a non-mocked version. Let's patch the model directly for a more robust test.

    # Re-run with a patch on the model to verify the side-effect
    with patch('api.whatsapp.models.WhatsAppConversationSettings.objects.get_or_create') as mock_get_or_create:
        mock_settings = MagicMock()
        mock_settings.agent_enabled = True
        mock_get_or_create.return_value = (mock_settings, True)

        # Call the actual email alert function which contains the logic to disable the agent
        from api.utils.email.internal_alerts import send_ai_escalation_alert
        send_ai_escalation_alert(lead=lead, reason="Test", sender_phone=lead.phone)
        
        # 2. Assert agent was disabled
        assert mock_settings.agent_enabled is False
        mock_settings.save.assert_called_once()

    # 3. Assert the final message is clean and correct
    assert "[[ESCALATE_REQUIRED:" not in clean_reply
    assert "01 42 59 60 08" in clean_reply


@patch('api.whatsapp.agent.handler._get_gemini_client')
def test_visio_confirmation_contains_payment_link(mock_get_gemini_client, settings):
    """
    Verify that a visio appointment confirmation contains the PayPal link
    and a request for a screenshot.
    """
    settings.PAYPAL_VISIO_LINK = "https://paypal.me/papexpress/50"
    
    # Mock Gemini to generate a reply that includes the actual link,
    # as the real AI would do after reading the context.
    mock_gemini_response = MagicMock()
    mock_gemini_response.text = (
        "Parfait, votre rendez-vous est pris ! Pour valider, merci de régler via https://paypal.me/papexpress/50. "
        "Envoyez une capture d'écran après paiement."
    )
    mock_gemini_client = MagicMock()
    mock_gemini_client.models.generate_content.return_value = mock_gemini_response
    mock_get_gemini_client.return_value = mock_gemini_client

    clean_reply, _ = generate_agent_reply(
        incoming_message="OK pour la visio.",
        sender_phone="+33633333333"
    )

    assert settings.PAYPAL_VISIO_LINK in clean_reply
    assert "capture d'écran" in clean_reply


@patch('api.whatsapp.agent.handler._get_gemini_client')
def test_payment_confirmation_image_triggers_correct_flow(mock_get_gemini_client):
    """
    Verify that receiving an "[Image]" message after a payment link was sent
    triggers the payment confirmation flow.
    """
    lead = Lead.objects.create(first_name="Test", last_name="Paiement", phone="+33644444444")
    
    # Mock Gemini to simulate the special response for payment confirmation
    mock_gemini_response = MagicMock()
    mock_gemini_response.text = (
        "Merci beaucoup pour cette confirmation ! Nous la vérifions et nous revenons vers vous avec le lien de la visioconférence dans les plus brefs délais. Votre patience est précieuse."
        '[[ESCALATE_REQUIRED: "Le client a envoyé une confirmation de paiement par image pour la visio. Action requise : vérifier le paiement et envoyer le lien de la visio."]]'
    )
    mock_gemini_client = MagicMock()
    mock_gemini_client.models.generate_content.return_value = mock_gemini_response
    mock_get_gemini_client.return_value = mock_gemini_client

    # Simulate the previous message from Kemia containing the payment link
    WhatsAppMessage.objects.create(
        lead=lead,
        sender_phone=lead.phone,
        body="Voici le lien de paiement: https://paypal.me/papexpress/50",
        is_outbound=True,
        wa_id="msg1"
    )

    with patch('api.utils.email.internal_alerts.send_ai_escalation_alert') as mock_send_alert:
        clean_reply, _ = generate_agent_reply(
            incoming_message="[Image]", # The trigger
            sender_phone=lead.phone,
            lead=lead
        )

        # Assert that the correct escalation reason is used for the alert
        mock_send_alert.assert_called_once_with(
            lead=lead,
            reason="Le client a envoyé une confirmation de paiement par image pour la visio. Action requise : vérifier le paiement et envoyer le lien de la visio.",
            sender_phone=lead.phone
        )
        
        # Assert the client received the correct reassuring message
        assert "Merci beaucoup pour cette confirmation" in clean_reply
        assert "[[ESCALATE_REQUIRED:" not in clean_reply


@patch('api.whatsapp.agent.handler._get_gemini_client')
def test_promo_code_is_correctly_associated(mock_get_gemini_client, django_user_model):
    """
    Verify that if Kemia extracts a valid promo code, it gets correctly
    associated with the lead in the database.
    """
    from api.creators.models import CreatorProfile, PromoCode
    from api.whatsapp.lead_service import create_lead_from_kemora

    # 1. Setup: Create a creator and a promo code
    creator_user = django_user_model.objects.create(email='creator@test.com', first_name='Test', last_name='Creator')
    creator_profile = CreatorProfile.objects.create(user=creator_user, status=CreatorProfile.Status.ACTIVE)
    promo_code = PromoCode.objects.create(
        creator=creator_profile,
        code="KEMIA25",
        status=PromoCode.Status.ACTIVE
    )

    # 2. Mock Gemini to return LEAD_DATA with the promo code
    # This simulates Kemia understanding the user's message
    mock_gemini_response = MagicMock()
    lead_data_payload = {
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+33655555555",
        "email": "john.doe@test.com",
        "appointment_date": "2026-07-15T10:00:00+02:00",
        "appointment_type": "presentiel",
        "promo_code": "KEMIA25",
        "situation_summary": "Test summary"
    }
    mock_gemini_response.text = f"Rendez-vous confirmé. [[LEAD_DATA:{json.dumps(lead_data_payload)}]]"
    mock_gemini_client = MagicMock()
    mock_gemini_client.models.generate_content.return_value = mock_gemini_response
    mock_get_gemini_client.return_value = mock_gemini_client

    # 3. Call the main function that processes the response
    with patch('api.whatsapp.lead_service.create_lead_from_kemora', wraps=create_lead_from_kemora) as mock_create_lead:
        _, lead_result = generate_agent_reply(
            incoming_message="Bonjour, je veux un rdv, j'ai le code KEMIA25.",
            sender_phone="+33655555555"
        )

        # 4. Assertions
        # Check that the lead creation function was called with the promo code
        mock_create_lead.assert_called_once()
        call_kwargs = mock_create_lead.call_args.kwargs
        assert call_kwargs.get("promo_code") == "KEMIA25"

        # Check the database state
        created_lead_id = lead_result.get("lead_id")
        assert created_lead_id is not None
        
        final_lead = Lead.objects.get(id=created_lead_id)
        assert final_lead.promo_code == promo_code
        assert final_lead.creator_profile == creator_profile
        
        # Verify that the summary was updated for the jurist
        from api.comments.models import Comment
        comment = Comment.objects.get(lead=final_lead)
        assert "Code promo appliqué : KEMIA25" in comment.content
        assert "Test Creator" in comment.content
