from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from api.documents.models import Document
from api.documents.serializers import DocumentSerializer
from api.utils.cloud.storage import store_client_document


class DocumentViewSet(viewsets.ModelViewSet):
    """
    CRUD des documents client, upload multi-fichiers, suppression cloud.
    """

    queryset = Document.objects.select_related("client", "document_type")
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()

        client_id = self.request.query_params.get("client")
        document_type_id = self.request.query_params.get("document_type")

        if client_id:
            qs = qs.filter(client_id=client_id)

        if document_type_id:
            qs = qs.filter(document_type_id=document_type_id)

        return qs

    def create(self, request, *args, **kwargs):
        """
        Upload un ou plusieurs fichiers.

        Params :
        - client (id) obligatoire
        - document_type (id) optionnel
        - files[] ou file
        """

        client_id = request.data.get("client") or request.query_params.get("client")
        document_type_id = request.data.get("document_type")

        if not client_id:
            return Response({"detail": "client ID requis"}, status=400)

        # 🔹 Client
        from api.clients.models import Client

        try:
            client = Client.objects.get(pk=client_id)
        except Client.DoesNotExist:
            return Response({"detail": "Client inexistant"}, status=404)

        # 🔹 DocumentType (optionnel)
        document_type = None
        if document_type_id:
            from api.document_types.models import DocumentType

            try:
                document_type = DocumentType.objects.get(pk=document_type_id)
            except DocumentType.DoesNotExist:
                return Response(
                    {"detail": "Type de document invalide"}, status=400
                )

        # 🔹 fichiers
        files = request.FILES.getlist("files") or [request.FILES.get("file")]
        files = [f for f in files if f]

        if not files:
            return Response({"detail": "Aucun fichier fourni"}, status=400)

        documents = []

        for file in files:
            # upload vers storage
            url = store_client_document(client, file, file.name)

            # création document
            doc = Document.objects.create(
                client=client,
                document_type=document_type,
                url=url,
            )
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
                from urllib.parse import unquote, urlparse

                from api.utils.cloud.scw.bucket_utils import delete_object

                parsed = urlparse(file_url)
                path = unquote(parsed.path).lstrip("/")

                parts = path.split("/")

                # enlève le prefix bucket si présent
                if len(parts) > 1:
                    key = "/".join(parts[1:])
                else:
                    key = parts[0]

                delete_object("documents", key)

            except Exception as e:
                print(f"Erreur suppression document du storage : {e}")

        return super().destroy(request, *args, **kwargs)