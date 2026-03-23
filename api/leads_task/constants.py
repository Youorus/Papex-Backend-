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

    COLORS = {
        TODO: "blue",
        IN_PROGRESS: "processing",
        DONE: "success",
        CANCELLED: "error",
    }