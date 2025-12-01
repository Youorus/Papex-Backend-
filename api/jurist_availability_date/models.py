from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model

User = get_user_model()


class JuristGlobalAvailability(models.Model):
    """
    Définit les créneaux globaux où il est possible de prendre rendez-vous
    avec n'importe quel juriste disponible.
    """

    AVAILABILITY_TYPE_CHOICES = [
        ('global', 'Disponibilité globale'),
        ('specific', 'Juriste spécifique'),
    ]

    availability_type = models.CharField(
        max_length=20,
        choices=AVAILABILITY_TYPE_CHOICES,
        default='global',
        help_text="Type de disponibilité : globale ou pour un juriste spécifique"
    )

    jurist = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='specific_availabilities',
        limit_choices_to={'is_staff': True},
        help_text="Juriste concerné (uniquement pour availability_type='specific')"
    )

    date = models.DateField(
        default=timezone.now,
        help_text="Date du créneau de disponibilité"
    )

    start_time = models.TimeField(
        help_text="Heure de début du créneau (HH:MM)"
    )

    end_time = models.TimeField(
        help_text="Heure de fin du créneau (HH:MM)"
    )

    slot_duration = models.IntegerField(
        default=30,
        validators=[MinValueValidator(15)],
        help_text="Durée de chaque créneau en minutes (min: 15)"
    )

    repeat_weekly = models.BooleanField(
        default=False,
        help_text="Si coché, ce créneau est répété chaque semaine au même jour"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Désactiver temporairement sans supprimer"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Disponibilité juriste"
        verbose_name_plural = "Disponibilités juristes"
        ordering = ["date", "start_time"]
        indexes = [
            models.Index(fields=['date', 'availability_type']),
            models.Index(fields=['jurist', 'date']),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        # Validation : juriste requis si type spécifique
        if self.availability_type == 'specific' and not self.jurist:
            raise ValidationError({
                'jurist': "Un juriste doit être sélectionné pour une disponibilité spécifique"
            })

        # Validation : pas de juriste si type global
        if self.availability_type == 'global' and self.jurist:
            raise ValidationError({
                'jurist': "Aucun juriste ne doit être sélectionné pour une disponibilité globale"
            })

        # Validation : heure de fin après heure de début
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({
                'end_time': "L'heure de fin doit être après l'heure de début"
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        jurist_info = f" - {self.jurist.get_full_name()}" if self.jurist else " - Tous juristes"
        base_str = (
            f"{self.date.strftime('%d/%m/%Y')} "
            f"de {self.start_time.strftime('%H:%M')} "
            f"à {self.end_time.strftime('%H:%M')} "
            f"({self.slot_duration}min){jurist_info}"
        )
        if self.repeat_weekly:
            base_str += " [répété]"
        if not self.is_active:
            base_str += " [inactif]"
        return base_str

    @property
    def duration_minutes(self):
        """Calcule la durée totale du créneau en minutes"""
        from datetime import datetime, timedelta
        start = datetime.combine(self.date, self.start_time)
        end = datetime.combine(self.date, self.end_time)
        return int((end - start).total_seconds() / 60)

    @property
    def available_slots_count(self):
        """Calcule le nombre de créneaux disponibles"""
        return self.duration_minutes // self.slot_duration

    def get_time_slots(self):
        """Retourne la liste des créneaux horaires disponibles"""
        from datetime import datetime, timedelta

        slots = []
        current = datetime.combine(self.date, self.start_time)
        end = datetime.combine(self.date, self.end_time)
        delta = timedelta(minutes=self.slot_duration)

        while current + delta <= end:
            slots.append({
                'start': current.time(),
                'end': (current + delta).time(),
            })
            current += delta

        return slots