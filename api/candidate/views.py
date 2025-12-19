from rest_framework import viewsets, filters, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Candidate
from .serializers import CandidateSerializer
from api.utils.cloud.storage import store_candidate_cv
from api.job.models import Job


class CandidateViewSet(viewsets.ModelViewSet):
    """
    CRUD des candidatures.

    Création :
    - multipart/form-data
    - champs requis :
        - job (slug ou id)
        - first_name
        - last_name
        - email
        - cv (fichier)
    """

    queryset = Candidate.objects.select_related("job")
    serializer_class = CandidateSerializer
    permission_classes = [AllowAny]

    filter_backends = [filters.OrderingFilter]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = super().get_queryset()

        job_slug = self.request.query_params.get("job")
        status_param = self.request.query_params.get("status")

        if job_slug:
            qs = qs.filter(job__slug=job_slug)

        if status_param:
            qs = qs.filter(status=status_param)

        return qs

    def create(self, request, *args, **kwargs):
        """
        Création d'une candidature avec upload du CV.
        """

        job_value = request.data.get("job")
        cv_file = request.FILES.get("cv")

        if not job_value:
            return Response(
                {"detail": "L’offre d’emploi est requise"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not cv_file:
            return Response(
                {"detail": "Le CV est requis"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Récupération de l'offre
        try:
            if str(job_value).isdigit():
                job = Job.objects.get(pk=job_value)
            else:
                job = Job.objects.get(slug=job_value)
        except Job.DoesNotExist:
            return Response(
                {"detail": "Offre d’emploi inexistante"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Création temporaire du candidat (sans CV)
        candidate = Candidate.objects.create(
            job=job,
            first_name=request.data.get("first_name", "").strip(),
            last_name=request.data.get("last_name", "").strip(),
            email=request.data.get("email", "").strip(),
        )

        # Upload du CV dans MinIO
        try:
            cv_url = store_candidate_cv(candidate, cv_file)
        except Exception as e:
            candidate.delete()
            return Response(
                {"detail": f"Erreur lors de l’upload du CV : {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        candidate.cv_url = cv_url
        candidate.save(update_fields=["cv_url"])

        serializer = self.get_serializer(candidate)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
