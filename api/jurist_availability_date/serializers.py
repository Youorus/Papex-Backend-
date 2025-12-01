# ==========================================
# BACKEND DJANGO - serializers.py
# api/jurist_availability_date/serializers.py
# ==========================================

from rest_framework import serializers
from django.contrib.auth import get_user_model
from api.jurist_availability_date.models import JuristGlobalAvailability

User = get_user_model()


class JuristGlobalAvailabilitySerializer(serializers.ModelSerializer):
    # ✅ Le champ jurist accepte un email (string) en entrée
    jurist = serializers.EmailField(write_only=True, required=False, allow_null=True)

    # ✅ En lecture, on retourne l'objet complet du juriste
    jurist_detail = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = JuristGlobalAvailability
        fields = [
            'id',
            'availability_type',
            'jurist',  # Email en écriture
            'jurist_detail',  # Objet complet en lecture
            'date',
            'start_time',
            'end_time',
            'slot_duration',
            'repeat_weekly',
            'is_active',
            'available_slots_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'available_slots_count']

    def get_jurist_detail(self, obj):
        """Retourne les infos du juriste en lecture"""
        if obj.jurist:
            return {
                'id': str(obj.jurist.id),
                'email': obj.jurist.email,
                'first_name': obj.jurist.first_name,
                'last_name': obj.jurist.last_name,
            }
        return None

    def validate(self, attrs):
        """Validation des données"""
        availability_type = attrs.get('availability_type')
        jurist_email = attrs.get('jurist')

        # ✅ Si spécifique, jurist (email) obligatoire
        if availability_type == 'specific':
            if not jurist_email:
                raise serializers.ValidationError({
                    'jurist': 'Un juriste doit être sélectionné pour une disponibilité spécifique'
                })

            # ✅ Rechercher le juriste par email
            try:
                jurist = User.objects.get(email=jurist_email, role='JURISTE')
                attrs['jurist'] = jurist  # Remplacer l'email par l'instance
            except User.DoesNotExist:
                raise serializers.ValidationError({
                    'jurist': f'Aucun juriste trouvé avec l\'email: {jurist_email}'
                })

        # ✅ Si global, jurist doit être null
        elif availability_type == 'global':
            attrs['jurist'] = None

        return attrs


class AvailabilityStatsSerializer(serializers.Serializer):
    total_availabilities = serializers.IntegerField()
    global_availabilities = serializers.IntegerField()
    specific_availabilities = serializers.IntegerField()
    total_slots = serializers.IntegerField()
    active_jurists = serializers.IntegerField()