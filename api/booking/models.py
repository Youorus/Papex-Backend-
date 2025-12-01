from django.db import models


class SlotQuota(models.Model):
    """
    Compteur atomique par créneau (start_at).
    - capacity vient des règles OpeningHours au moment du get_or_create
    - booked s'incrémente/décrémente transactionnellement
    """

    start_at = models.DateTimeField(unique=True, db_index=True)
    capacity = models.PositiveIntegerField()
    booked = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Quota de créneau"
        verbose_name_plural = "Quotas de créneau"

    @property
    def remaining(self) -> int:
        return max(self.capacity - self.booked, 0)

    def __str__(self) -> str:
        return f"{self.start_at} — {self.booked}/{self.capacity}"
