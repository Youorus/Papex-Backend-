# users/test_models.py
import uuid

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils.translation import gettext_lazy as _

from api.users.roles import UserRoles


class CustomUserManager(BaseUserManager):
    """
    Gestionnaire personnalisé pour le modèle User.
    Fournit les méthodes de création d'utilisateur et superutilisateur.
    """

    def create_user(
        self,
        email,
        first_name,
        last_name,
        password=None,
        role=UserRoles.CONSEILLER,
        **extra_fields,
    ):
        """
        Crée un utilisateur avec email, prénom, nom, mot de passe et rôle.
        """
        if not email:
            raise ValueError(_("L'adresse email est obligatoire."))
        if not password:
            raise ValueError(_("Un mot de passe est requis."))

        email = self.normalize_email(email)
        user = self.model(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            **extra_fields,
        )
        user.set_password(password)
        user.set_role_permissions()
        user.save(using=self._db)
        return user

    def create_superuser(
        self, email, first_name, last_name, password=None, **extra_fields
    ):
        """
        Crée un superutilisateur (admin) avec tous les droits.
        """
        extra_fields.setdefault("role", UserRoles.ADMIN)
        user = self.create_user(email, first_name, last_name, password, **extra_fields)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    """
    Modèle utilisateur personnalisé.
    Utilise l'email comme identifiant et un UUID comme clé primaire.
    Gère les rôles, les permissions, l'activation et les métadonnées.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID unique"),
    )

    email = models.EmailField(
        unique=True,
        verbose_name=_("adresse email"),
        help_text=_("Adresse utilisée pour la connexion"),
    )

    first_name = models.CharField(
        max_length=150, verbose_name=_("prénom"), help_text=_("Prénom de l'utilisateur")
    )

    last_name = models.CharField(
        max_length=150, verbose_name=_("nom"), help_text=_("Nom de l'utilisateur")
    )

    role = models.CharField(
        max_length=32,
        choices=UserRoles.choices,
        default=UserRoles.CONSEILLER,
        verbose_name=_("rôle"),
        help_text=_("Rôle attribué à l'utilisateur"),
    )

    is_staff = models.BooleanField(
        default=False,
        verbose_name=_("membre du staff"),
        help_text=_("Peut accéder à l'admin Django"),
    )

    is_superuser = models.BooleanField(
        default=False,
        verbose_name=_("superutilisateur"),
        help_text=_("Possède tous les droits"),
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("actif"),
        help_text=_("Contrôle si l'utilisateur peut se connecter"),
    )

    date_joined = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("date d'inscription"),
        help_text=_("Date de création du compte"),
    )

    avatar = models.URLField(
        blank=True,
        null=True,
        max_length=500,
        verbose_name=_("avatar"),
        help_text=_("URL de la photo de profil"),
    )

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name", "role"]

    class Meta:
        verbose_name = _("utilisateur")
        verbose_name_plural = _("utilisateurs")
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["email"], name="user_email_idx"),
            models.Index(fields=["date_joined"], name="user_joined_idx"),
        ]

    def __str__(self):
        """Représentation textuelle de l'utilisateur."""
        return f"{self.email} ({self.get_full_name()})"

    def get_full_name(self):
        """Retourne le prénom + nom complet."""
        return f"{self.first_name} {self.last_name}"

    def get_short_name(self):
        """Retourne uniquement le prénom."""
        return self.first_name

    def set_role_permissions(self):
        """
        Définit automatiquement les permissions is_staff et is_superuser en fonction du rôle.
        """
        if self.role == UserRoles.ADMIN:
            self.is_staff = True
            self.is_superuser = True
        else:
            self.is_staff = True  # peut adapter selon ton système
            self.is_superuser = False

    def save(self, *args, **kwargs):
        """
        Sauvegarde de l'utilisateur en mettant à jour les permissions liées au rôle.
        """
        self.set_role_permissions()
        super().save(*args, **kwargs)
