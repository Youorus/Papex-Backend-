from api.creators.models import PromoCode
from api.leads.models import Lead
from api.leads.serializers import LeadPromoCodeSerializer
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class LeadPromoCodeView(APIView):
    def put(self, request, lead_id):
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response({"error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = LeadPromoCodeSerializer(data=request.data)
        if serializer.is_valid():
            code = serializer.validated_data['code']
            try:
                promo_code_obj = PromoCode.objects.select_related('creator__user').get(
                    code__iexact=code.strip(),
                    status=PromoCode.Status.ACTIVE
                )

                lead.promo_code = promo_code_obj
                lead.creator_profile = promo_code_obj.creator
                lead.save()

                return Response({
                    "success": "Promo code associated.",
                    "promo_code_details": {
                        "code": promo_code_obj.code,
                        "creator_email": promo_code_obj.creator.user.email
                    }
                }, status=status.HTTP_200_OK)

            except PromoCode.DoesNotExist:
                return Response({"error": "Invalid or inactive promo code."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, lead_id):
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response({"error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)

        lead.promo_code = None
        lead.creator_profile = None
        lead.save()

        return Response(status=status.HTTP_204_NO_CONTENT)
