# api/urls.py

from django.urls import include, path

api_urlpatterns = [
    # Leads - gestion des leads (clients/prospects)
    path("leads/", include("api.leads.urls")),
    # Utilisateurs - gestion des comptes users (création, login, rôles)
    path("users/", include("api.users.urls")),
    # Clients - fiche client complète (état civil, demandes, etc)
    path("clients/", include("api.clients.urls")),
    # Contrats - gestion des contrats liés aux clients/services
    path("contracts/", include("api.contracts.urls")),
    # Paiements/Recus - gestion des reçus et paiements clients
    path("receipts/", include("api.payments.urls")),
    # Services - liste des services (ex: titre de séjour, naturalisation, etc)
    path("services/", include("api.services.urls")),
    path("opening-hours/", include("api.opening_hours.urls")),
    path("special-closing-periods/", include("api.special_closing_period.urls")),
    path("specialclosing/", include("api.special_closing_period.urls")),
    path("jurist-appointments/", include("api.jurist_appointment.urls")),
    # Commentaires - gestion des commentaires liés à un lead/client
    path("comments/", include("api.comments.urls")),
    # Statuts de leads (dynamique, customisable)
    path("lead-statuses/", include("api.lead_status.urls")),
    path("jurist-global-availability/", include("api.jurist_availability_date.urls")),
    path("user-unavailability/", include("api.user_unavailability.urls")),
    # Statuts de dossier (pour contrats ou demandes)
    path("statut-dossiers/", include("api.statut_dossier.urls")),
    path("statut-dossiers-internes/", include("api.statut_dossier_interne.urls")),
    # Documents clients (upload et gestion)
    path("documents/", include("api.documents.urls")),
    path("booking/", include("api.booking.urls")),
    path("appointments/", include("api.appointment.urls")),
    # Gestion des avatars utilisateurs (upload/profil)
    path("avatars/", include("api.profile.urls")),
    # Authentification (login, refresh, register si besoin)
    path("auth/", include("api.custom_auth.urls")),
    # Ajoute d'autres modules ici au besoin
]

urlpatterns = [
    path("", include(api_urlpatterns)),
]
