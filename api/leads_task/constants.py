"""
api/leads_task/constants.py
"""


class LeadTaskStatus:
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"

    CHOICES = [
        (TODO, "À faire"),
        (IN_PROGRESS, "En cours"),
        (DONE, "Terminé"),
        (CANCELLED, "Annulé"),
    ]


class LeadTaskPriority:
    MEDIUM = "medium"
    URGENT = "urgent"

    CHOICES = [
        (MEDIUM, "Normale"),
        (URGENT, "Urgente"),
    ]

    COLOR_MAP = {
        MEDIUM: "#1677ff",
        URGENT: "#ff4d4f",
    }