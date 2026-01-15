from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .tasks import trigger_call_task
import logging

logger = logging.getLogger(__name__)


class ClickToCallView(APIView):

    def _format_number(self, phone: str) -> str:
        """
        Utilitaire interne pour nettoyer le numéro pour OVH.
        Convertit +33 ou 06... en 0033...
        """
        if not phone:
            return ""

        # 1. Supprimer les espaces, points, tirets
        clean = phone.replace(" ", "").replace(".", "").replace("-", "")

        # 2. Remplacer le "+" initial par "00" (ex: +336... -> 00336...)
        if clean.startswith("+"):
            clean = clean.replace("+", "00", 1)

        # 3. Gérer le format français local (ex: 0612... -> 0033612...)
        # On vérifie que ça commence par 0 mais PAS par 00
        elif clean.startswith("0") and not clean.startswith("00"):
            clean = "0033" + clean[1:]

        return clean

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