"""
api/leads/events/services.py
"""

from .models import LeadEvent


class LeadEventService:

    @staticmethod
    def log(lead, event_code, actor=None, data=None, note=""):

        return LeadEvent.log(
            lead=lead,
            event_code=event_code,
            actor=actor,
            data=data,
            note=note,
        )