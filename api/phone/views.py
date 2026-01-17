from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .tasks import trigger_call_task
import logging

logger = logging.getLogger(__name__)


class ClickToCallView(APIView):

    def _format_number(self, phone: str) -> str:
        """
        Format E.164 pour OVH SIP
        Résultat final : +33XXXXXXXXX
        """
        if not phone:
            return ""

        # Nettoyage
        clean = (
            phone.replace(" ", "")
            .replace(".", "")
            .replace("-", "")
        )

        # Déjà au bon format
        if clean.startswith("+"):
            return clean

        # Format 00 -> +
        if clean.startswith("00"):
            return "+" + clean[2:]

        # Format français local 06 / 07 / 01...
        if clean.startswith("0"):
            return "+33" + clean[1:]

        # fallback sécurité
        return "+" + clean

    def post(self, request):
        raw_phone_number = request.data.get('phone_number')

        print(f"DEBUG - Reçu brut : {raw_phone_number}")

        if not raw_phone_number:
            return Response(
                {"error": "Numéro de téléphone manquant"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- FORMATAGE ICI ---
        formatted_number = self._format_number(raw_phone_number)

        print(f"DEBUG - Formaté pour OVH : {formatted_number}")

        # On envoie le numéro PROPRE à la tâche Celery
        trigger_call_task.delay(formatted_number)

        return Response(
            {"message": "Appel en cours de lancement sur votre softphone..."},
            status=status.HTTP_200_OK
        )