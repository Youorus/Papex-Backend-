import pytest
from unittest.mock import patch, MagicMock
from api.whatsapp.agent.engine import _extract_escalation_reason, _strip_markers
from api.whatsapp.lead_service import appointment_slot_lock
from django.core.cache import cache
import datetime

def test_escalation_extraction():
    text = "Je vous aide de suite. [[ESCALATE_REQUIRED: \"Client agressif\"]] "
    reason = _extract_escalation_reason(text)
    assert reason == "Client agressif"
    
    clean = _strip_markers(text)
    assert clean == "Je vous aide de suite."

@pytest.mark.django_db
def test_appointment_double_booking_prevention():
    dt = datetime.datetime(2026, 6, 1, 10, 0)
    
    # 1er verrouillage
    with appointment_slot_lock(dt) as acquired1:
        assert acquired1 is True
        
        # Tentative de 2ème verrouillage pendant que le 1er est actif
        with appointment_slot_lock(dt) as acquired2:
            assert acquired2 is False
            
    # Après libération, on peut reverrouiller
    with appointment_slot_lock(dt) as acquired3:
        assert acquired3 is True
