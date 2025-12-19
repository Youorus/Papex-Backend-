"""
Vues pour l'application Jobs.
Endpoints REST pour gérer les offres d'emploi.
"""

import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api.job.models import Job
from api.job.serializers import JobSerializer, JobListSerializer
from api.job.permissions import IsJobEditor

logger = logging.getLogger(__name__)


class JobViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les offres d'emploi.

    Endpoints principaux :
    - GET    /api/jobs/                    : liste des offres actives
    - GET    /api/jobs/{slug}/             : détail d'une offre
    - POST   /api/jobs/                    : créer une offre (rôles internes)
    - PUT    /api/jobs/{slug}/             : modifier (rôles internes)
    - PATCH  /api/jobs/{slug}/             : modifier partiellement (rôles internes)
    - DELETE /api/jobs/{slug}/             : supprimer (rôles internes)

    Endpoints custom :
    - GET  /api/jobs/active/
    - GET  /api/jobs/all/                  : toutes les offres (rôles internes)
    - POST /api/jobs/{slug}/toggle-status/ : activer/désactiver
    """

    queryset = Job.objects.all()
    lookup_field = "slug"
    permission_classes = [IsJobEditor]

    # -------------------------
    # Queryset
    # -------------------------
    def get_queryset(self):
        """
        - Public / utilisateurs standards : offres actives uniquement
        - Rôles internes : toutes les offres
        """
        qs = Job.objects.all()
        user = self.request.user

        if (
            user.is_authenticated
            and getattr(user, "role", None) in IsJobEditor.ALLOWED_ROLES
        ):
            return qs

        return qs.filter(is_active=True)

    # -------------------------
    # Serializer
    # -------------------------
    def get_serializer_class(self):
        """
        - Liste & active : serializer allégé
        - Détail & écriture : serializer complet
        """
        if self.action in {"list", "active"}:
            return JobListSerializer
        return JobSerializer

    # -------------------------
    # Overrides DRF
    # -------------------------
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        logger.info("📋 Liste des offres demandée (%s résultats)", queryset.count())
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        job = self.get_object()
        serializer = self.get_serializer(job)

        logger.info("📄 Offre consultée : %s (%s)", job.title, job.slug)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = serializer.save()

        logger.info("✅ Offre créée : %s (%s)", job.title, job.slug)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        job = self.get_object()

        serializer = self.get_serializer(job, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        job = serializer.save()

        logger.info("✏️ Offre mise à jour : %s (%s)", job.title, job.slug)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        job = self.get_object()
        title = job.title
        slug = job.slug

        job.delete()

        logger.warning("🗑️ Offre supprimée : %s (%s)", title, slug)
        return Response(
            {"detail": f"L'offre « {title} » a été supprimée avec succès."},
            status=status.HTTP_200_OK,
        )

    # -------------------------
    # Actions custom
    # -------------------------
    @action(
        detail=False,
        methods=["get"],
        url_path="active",
        permission_classes=[AllowAny],
    )
    def active(self, request):
        """
        GET /api/jobs/active/
        """
        queryset = Job.objects.filter(is_active=True)
        serializer = JobListSerializer(queryset, many=True)

        logger.info("🟢 Offres actives demandées (%s résultats)", queryset.count())
        return Response({
            "count": queryset.count(),
            "results": serializer.data,
        })

    @action(
        detail=False,
        methods=["get"],
        url_path="all",
        permission_classes=[IsJobEditor],
    )
    def all(self, request):
        """
        GET /api/jobs/all/
        """
        queryset = Job.objects.all()
        serializer = JobSerializer(queryset, many=True)

        active_count = queryset.filter(is_active=True).count()
        inactive_count = queryset.filter(is_active=False).count()

        logger.info(
            "📊 Toutes les offres demandées (%s actives / %s inactives)",
            active_count,
            inactive_count,
        )

        return Response({
            "count": queryset.count(),
            "active_count": active_count,
            "inactive_count": inactive_count,
            "results": serializer.data,
        })

    @action(
        detail=True,
        methods=["post"],
        url_path="toggle-status",
        permission_classes=[IsJobEditor],
    )
    def toggle_status(self, request, slug=None):
        """
        POST /api/jobs/{slug}/toggle-status/
        """
        job = self.get_object()
        job.is_active = not job.is_active
        job.save(update_fields=["is_active"])

        status_text = "activée" if job.is_active else "désactivée"
        logger.info("🔄 Offre %s : %s (%s)", status_text, job.title, job.slug)

        return Response({
            "detail": f"L'offre « {job.title} » a été {status_text}.",
            "is_active": job.is_active,
        })