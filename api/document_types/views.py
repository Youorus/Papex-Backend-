from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import DocumentType
from .serializers import DocumentTypeSerializer


class DocumentTypeViewSet(viewsets.ModelViewSet):
    queryset = DocumentType.objects.all()
    serializer_class = DocumentTypeSerializer
    permission_classes = [IsAuthenticated]