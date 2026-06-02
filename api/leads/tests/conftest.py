import pytest
from api.lead_status.models import LeadStatus

@pytest.fixture
def lead_status(db):
    return LeadStatus.objects.create(label="Test Status", code="TEST")
