from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from api.documents.models import Document
from api.documents.serializers import DocumentSerializer
from api.utils.cloud.storage import store_client_document


class DocumentViewSet(viewsets.ModelViewSet):
    """
    CRUD des documents client, upload multi-fichiers, suppression cloud.
    """

    queryset = Document.objects.select_related("client")
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        client_id = self.request.query_params.get("client")
        if client_id:
            qs = qs.filter(client_id=client_id)
        return qs

    def create(self, request, *args, **kwargs):
        """
        Upload un ou plusieurs fichiers.
        - files[] ou file
        - client ID en POST ou URL
        """
        client_id = request.data.get("client") or request.query_params.get("client")
        if not client_id:
            return Response({"detail": "client ID requis"}, status=400)
        from api.clients.models import Client

        try:
            client = Client.objects.get(pk=client_id)
        except Client.DoesNotExist:
            return Response({"detail": "Client inexistant"}, status=404)
        files = request.FILES.getlist("files") or [request.FILES.get("file")]
        files = [f for f in files if f]

        documents = []
        from api.storage_backends import MinioDocumentStorage

        storage = MinioDocumentStorage()
        for file in files:
            url = store_client_document(client, file, file.name)
            doc = Document.objects.create(client=client, url=url)
            documents.append(doc)

        serializer = self.get_serializer(documents, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        """
        Supprime en DB + bucket cloud (S3/Scaleway).
        """
        instance = self.get_object()
        file_url = instance.url
        if file_url:
            try:
                from django.conf import settings

                from api.utils.cloud.scw.bucket_utils import delete_object

                bucket_name = settings.SCW_BUCKETS["documents"]
                split_token = f"/{bucket_name}/"
                if split_token in file_url:
                    path = file_url.split(split_token, 1)[1]
                else:
                    path = file_url.split("/")[-2] + "/" + file_url.split("/")[-1]
                if path.startswith("/"):
                    path = path[1:]
                delete_object("documents", path)
            except Exception as e:
                print(f"Erreur suppression document du storage : {e}")
        return super().destroy(request, *args, **kwargs)
