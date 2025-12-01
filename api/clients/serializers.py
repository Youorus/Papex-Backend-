"""
Sérialiseurs pour l’application Clients.

Ce module définit le serializer principal pour le modèle Client. Il prend en charge :
- la sérialisation complète des données client pour les opérations d’API (lecture et écriture),
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

    # Champ write-only : permet d'assigner le type_demande par son id (POST/PATCH)
    type_demande_id = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(),
        source="type_demande",
        write_only=True,
        required=False,
        allow_null=True,
    )

    # Champ read-only : permet d'afficher le service détaillé côté lecture (GET)
    type_demande = ServiceSerializer(read_only=True)

    class Meta:
        model = Client
        # On exclut le champ lead (clé étrangère interne)
        exclude = ["lead"]

    # =========================
    #  VALIDATIONS INDIVIDUELLES
    # =========================

    def validate_date_naissance(self, value):
        """Vérifie que la date de naissance n'est pas dans le futur."""
        if value > timezone.now().date():
            raise serializers.ValidationError(
                "La date de naissance ne peut pas être dans le futur."
            )
        return value

    def validate_date_entree_france(self, value):
        """Vérifie que la date d’entrée en France n'est pas dans le futur."""
        if value > timezone.now().date():
            raise serializers.ValidationError(
                "La date d’entrée en France ne peut pas être dans le futur."
            )
        return value

    def validate_date_depuis_sans_emploi(self, value):
        """Vérifie que la date sans emploi n'est pas dans le futur."""
        if value and value > timezone.now().date():
            raise serializers.ValidationError("La date ne peut pas être dans le futur.")
        return value

    def validate_date_derniere_oqtf(self, value):
        """Vérifie que la date de dernière OQTF n'est pas dans le futur."""
        if value and value > timezone.now().date():
            raise serializers.ValidationError("La date ne peut pas être dans le futur.")
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
        if value and len(value) > 255:
            raise serializers.ValidationError("Maximum 255 caractères autorisés.")
        return value

    def validate_demande_formulee_precise(self, value):
        """Limite la taille du champ demande_formulee_precise."""
        if value and len(value) > 255:
            raise serializers.ValidationError("Maximum 255 caractères autorisés.")
        return value

    def validate_type_demande(self, value):
        """Oblige à sélectionner un type de demande."""
        if not value:
            raise serializers.ValidationError(
                "Veuillez sélectionner un type de demande."
            )
        return value

    # =========================
    #  VALIDATIONS CROISÉES
    # =========================
    def validate(self, data):
        """
        Validation croisée des champs du formulaire Client.
        Vérifie : dépendances logiques, valeurs négatives, etc.
        """
        errors = {}
        is_partial = getattr(self, "partial", False)

        # Type de visa obligatoire si a_un_visa est True
        if (
            (not is_partial or "type_visa" in data)
            and data.get("a_un_visa")
            and not data.get("type_visa")
        ):
            errors["type_visa"] = "Veuillez sélectionner un type de visa."

        # Date d'expiration du visa obligatoire si a_un_visa est True
        if (
            (not is_partial or "date_expiration_visa" in data)
            and data.get("a_un_visa")
            and not data.get("date_expiration_visa")
        ):
            errors["date_expiration_visa"] = "Veuillez indiquer la date d'expiration du visa."

        # Domaine d'activité obligatoire si situation_pro renseignée
        if (
            (not is_partial or "domaine_activite" in data)
            and data.get("situation_pro")
            and not data.get("domaine_activite")
        ):
            errors["domaine_activite"] = "Veuillez indiquer votre domaine d’activité."

        # Validation souple pour le compte Démarches Simplifiées
        if data.get("has_demarche_simplifiee_account"):

            existing_email = getattr(self.instance, "demarche_simplifiee_email", None) if self.instance else None
            existing_password = getattr(self.instance, "demarche_simplifiee_password", None) if self.instance else None

            email = data.get("demarche_simplifiee_email", existing_email)
            password = data.get("demarche_simplifiee_password", existing_password)

            # Si l'utilisateur commence à remplir (email OU password), on exige l’autre
            if email and not password:
                errors["demarche_simplifiee_password"] = (
                    "Veuillez renseigner le mot de passe du compte Démarches Simplifiées."
                )

            if password and not email:
                errors["demarche_simplifiee_email"] = (
                    "Veuillez renseigner l'email du compte Démarches Simplifiées."
                )

        # Nombre d'enfants doit être positif
        if (not is_partial or "nombre_enfants" in data) and data.get(
            "nombre_enfants"
        ) is not None:
            if data["nombre_enfants"] < 0:
                errors["nombre_enfants"] = "Veuillez saisir un nombre valide."

        # Nombre d'enfants français doit être positif
        if (not is_partial or "nombre_enfants_francais" in data) and data.get(
            "nombre_enfants_francais"
        ) is not None:
            if data["nombre_enfants_francais"] < 0:
                errors["nombre_enfants_francais"] = "Veuillez saisir un nombre valide."

        # Nombre de fiches de paie doit être positif
        if (not is_partial or "nombre_fiches_paie" in data) and data.get(
            "nombre_fiches_paie"
        ) is not None:
            if data["nombre_fiches_paie"] < 0:
                errors["nombre_fiches_paie"] = "Veuillez saisir un nombre valide."

        if errors:
            raise serializers.ValidationError(errors)

        return data
