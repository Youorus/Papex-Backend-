# api/opening_hours/test_serializers.py
from rest_framework import serializers

from api.opening_hours.models import OpeningHours


class OpeningHoursSerializer(serializers.ModelSerializer):
    # Accepte "09:00" ou "09:00:00"
    open_time = serializers.TimeField(
        allow_null=True, required=False, input_formats=["%H:%M", "%H:%M:%S"]
    )
    close_time = serializers.TimeField(
        allow_null=True, required=False, input_formats=["%H:%M", "%H:%M:%S"]
    )

    # PATCH partiel => pas requis
    slot_duration_minutes = serializers.IntegerField(
        min_value=5, max_value=480, required=False
    )
    capacity_per_slot = serializers.IntegerField(
        min_value=1, max_value=1000, required=False
    )
    is_active = serializers.BooleanField(required=False)

    class Meta:
        model = OpeningHours
        fields = (
            "id",
            "day_of_week",
            "open_time",
            "close_time",
            "slot_duration_minutes",
            "capacity_per_slot",
            "is_active",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        """
        Règles de validation métier :
        - Si is_active True -> open_time et close_time doivent être renseignés et open < close.
        - Si une heure est fournie, l'autre doit l'être aussi (sauf si is_active False).
        """
        # instance existante + attrs patchés => on reconstitue l’état final
        instance = getattr(self, "instance", None)

        def final_value(name, default=None):
            if attrs.get(name) is not None or name in attrs:
                return attrs.get(name)
            return getattr(instance, name) if instance is not None else default

        is_active = final_value("is_active", True)
        open_time = final_value("open_time", None)
        close_time = final_value("close_time", None)

        # Si actif, il faut deux heures cohérentes
        if is_active:
            if open_time is None or close_time is None:
                raise serializers.ValidationError(
                    {
                        "open_time": "Requis si le jour est actif.",
                        "close_time": "Requis si le jour est actif.",
                    }
                )
            if open_time >= close_time:
                raise serializers.ValidationError(
                    {
                        "close_time": "La fermeture doit être strictement après l’ouverture."
                    }
                )
        else:
            # Jour fermé : on autorise heures nulles ou renseignées (elles seront ignorées côté planning)
            # Si tu préfères forcer à null quand inactif, dé-commente ci-dessous :
            # attrs["open_time"] = None
            # attrs["close_time"] = None
            pass

        # Cohérence si une seule heure fournie alors que l’autre manque
        if (open_time is None) ^ (close_time is None):  # XOR
            # si actif, on a déjà levé au-dessus; si inactif on tolère
            if is_active:
                raise serializers.ValidationError(
                    {
                        "non_field_errors": "Si le jour est actif, ouverture et fermeture sont toutes deux requises."
                    }
                )

        return attrs
