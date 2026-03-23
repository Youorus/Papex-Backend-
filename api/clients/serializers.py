"""
Sérialiseurs pour l'application Clients.

Ce module définit le serializer principal pour le modèle Client. Il prend en charge :
- la sérialisation complète des données client pour les opérations d'API (lecture et écriture),
- la validation individuelle et croisée des champs du formulaire,
- la gestion du champ `type_demande` (lecture avec détails, écriture via l'ID).

Il garantit que les données saisies sont cohérentes et conformes aux règles métier avant enregistrement.
"""

from django.utils import timezone
from rest_framework import serializers

from api.clients.models import Client
from api.services.models import Service
from api.services.serializers import ServiceSerializer


class ClientSerializer(serializers.ModelSerializer):
    """
    Serializer principal pour le modèle Client.
    Gère la sérialisation complète des données client,
    la validation individuelle et croisée des champs,
    ainsi que la gestion du type de demande (service).
    """

    # Champ write-only : permet d'assigner le type_demande par son id (POST/PATCH)
    type_demande_id = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(),
        source="type_demande",
        write_only=True,
        required=False,
        allow_null=True,
    )

    # Champ read-only : permet d'afficher le service détaillé côté lecture (GET)
    type_demande = ServiceSerializer(read_only=True)

    # 🔥 Exposer l'ID du lead sans ramener tout l'objet
    lead_id = serializers.IntegerField(source="lead.id", read_only=True)

    class Meta:
        model = Client
        exclude = ["lead"]
        extra_fields = ["lead_id"]

    # ─────────────────────────────────────────────────────────────────────────
    # VALIDATIONS INDIVIDUELLES
    # 🔥 Tous les validateurs de dates gardent un guard `if value is None`
    #    car en mode partial=True (PATCH), DRF peut appeler le validateur
    #    avec None si le champ est explicitement envoyé à null — sans ce guard,
    #    la comparaison `value > date` lève TypeError.
    # ─────────────────────────────────────────────────────────────────────────

    def validate_date_naissance(self, value):
        """Vérifie que la date de naissance n'est pas dans le futur."""
        if value is None:
            return value
        if value > timezone.now().date():
            raise serializers.ValidationError(
                "La date de naissance ne peut pas être dans le futur."
            )
        return value

    def validate_date_entree_france(self, value):
        """Vérifie que la date d'entrée en France n'est pas dans le futur."""
        if value is None:
            return value
        if value > timezone.now().date():
            raise serializers.ValidationError(
                "La date d'entrée en France ne peut pas être dans le futur."
            )
        return value

    def validate_date_depuis_sans_emploi(self, value):
        """Vérifie que la date sans emploi n'est pas dans le futur."""
        if value is None:
            return value
        if value > timezone.now().date():
            raise serializers.ValidationError("La date ne peut pas être dans le futur.")
        return value

    def validate_date_derniere_oqtf(self, value):
        """Vérifie que la date de dernière OQTF n'est pas dans le futur."""
        if value is None:
            return value
        if value > timezone.now().date():
            raise serializers.ValidationError("La date ne peut pas être dans le futur.")
        return value

    def validate_last_anef_notification_date(self, value):
        """Vérifie que la date de notification ANEF n'est pas dans le futur."""
        if value is None:
            return value
        if value > timezone.now().date():
            raise serializers.ValidationError("La date ne peut pas être dans le futur.")
        return value

    def validate_date_expiration_visa(self, value):
        """Accepte les dates d'expiration passées (visa expiré) — pas de contrainte future."""
        return value

    def validate_code_postal(self, value):
        """Vérifie la validité du code postal."""
        if value and (not value.isdigit() or not (4 <= len(value) <= 5)):
            raise serializers.ValidationError(
                "Le code postal doit contenir 4 ou 5 chiffres."
            )
        return value

    def validate_adresse(self, value):
        """Vérifie que l'adresse a une longueur minimale."""
        if value and len(value.strip()) < 5:
            raise serializers.ValidationError(
                "L'adresse est trop courte (minimum 5 caractères)."
            )
        return value

    def validate_ville(self, value):
        """Vérifie la longueur du nom de la ville."""
        if value and len(value.strip()) < 2:
            raise serializers.ValidationError("Le nom de la ville est trop court.")
        return value

    def validate_remarques(self, value):
        """Limite la taille des remarques."""
        if value and len(value) > 2000:
            raise serializers.ValidationError("Maximum 2000 caractères autorisés.")
        return value

    def validate_demande_formulee_precise(self, value):
        """Limite la taille du champ demande_formulee_precise."""
        if value and len(value) > 255:
            raise serializers.ValidationError("Maximum 255 caractères autorisés.")
        return value

    def validate_type_demande(self, value):
        """
        En création (POST) : type_demande obligatoire.
        En mise à jour partielle (PATCH) : on accepte null/absent.
        """
        is_partial = getattr(self, "partial", False)
        if not is_partial and not value:
            raise serializers.ValidationError(
                "Veuillez sélectionner un type de demande."
            )
        return value

    # ─────────────────────────────────────────────────────────────────────────
    # VALIDATIONS CROISÉES
    # ─────────────────────────────────────────────────────────────────────────

    def validate(self, data):
        """
        Validation croisée des champs du formulaire Client.
        Vérifie : dépendances logiques, valeurs négatives, etc.
        En mode partial (PATCH), on ne valide que les champs effectivement envoyés.
        """
        errors = {}
        is_partial = getattr(self, "partial", False)

        # ── Visa ──
        if (not is_partial or "type_visa" in data) and data.get("a_un_visa") and not data.get("type_visa"):
            errors["type_visa"] = "Veuillez sélectionner un type de visa."

        if (not is_partial or "date_expiration_visa" in data) and data.get("a_un_visa") and not data.get("date_expiration_visa"):
            errors["date_expiration_visa"] = "Veuillez indiquer la date d'expiration du visa."

        # ── Situation pro ──
        if (not is_partial or "domaine_activite" in data) and data.get("situation_pro") and not data.get("domaine_activite"):
            errors["domaine_activite"] = "Veuillez indiquer votre domaine d'activité."

        # ── Démarches Simplifiées ──
        if data.get("has_demarche_simplifiee_account"):
            existing_email    = getattr(self.instance, "demarche_simplifiee_email",    None) if self.instance else None
            existing_password = getattr(self.instance, "demarche_simplifiee_password", None) if self.instance else None

            email    = data.get("demarche_simplifiee_email",    existing_email)
            password = data.get("demarche_simplifiee_password", existing_password)

            if email and not password:
                errors["demarche_simplifiee_password"] = (
                    "Veuillez renseigner le mot de passe du compte Démarches Simplifiées."
                )
            if password and not email:
                errors["demarche_simplifiee_email"] = (
                    "Veuillez renseigner l'email du compte Démarches Simplifiées."
                )

        # ── Comptages positifs ──
        for field in ("nombre_enfants", "nombre_enfants_francais", "nombre_fiches_paie"):
            if (not is_partial or field in data) and data.get(field) is not None:
                if data[field] < 0:
                    errors[field] = "Veuillez saisir un nombre valide (≥ 0)."

        if errors:
            raise serializers.ValidationError(errors)

        return data