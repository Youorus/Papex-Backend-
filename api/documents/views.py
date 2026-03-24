import io
import unicodedata
import re
import zipfile

import requests
from django.http import StreamingHttpResponse
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from api.documents.models import Document
from api.documents.serializers import DocumentSerializer
from api.utils.cloud.storage import store_client_document


# ──────────────────────────────────────────────────────────────
# Helpers nommage
# ──────────────────────────────────────────────────────────────

def _slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    value = re.sub(r"[\s\-]+", "_", value)
    return value


def _build_filename(client, document_type, original_name: str, index: int = 0) -> str:
    """
    Construit un nom de fichier lisible :
      {prenom_nom|entreprise}_{type_document}[_{index}].{ext}
    """
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else "bin"

    client_parts = []
    if hasattr(client, "first_name") and client.first_name:
        client_parts.append(client.first_name)
    if hasattr(client, "last_name") and client.last_name:
        client_parts.append(client.last_name)
    if not client_parts and hasattr(client, "company_name") and client.company_name:
        client_parts.append(client.company_name)
    if not client_parts:
        client_parts.append(f"client_{client.pk}")

    client_slug = _slugify(" ".join(client_parts))
    type_slug   = _slugify(document_type.name) if document_type else "document"
    suffix      = f"_{index}" if index > 0 else ""

    return f"{client_slug}_{type_slug}{suffix}.{ext}"


def _extract_s3_key(url: str) -> str:
    """Extrait la clé S3 depuis l'URL stockée en base (sans le bucket)."""
    from urllib.parse import unquote, urlparse
    parsed = urlparse(url)
    path   = unquote(parsed.path).lstrip("/")
    parts  = path.split("/")
    return "/".join(parts[1:]) if len(parts) > 1 else parts[0]


def _delete_from_bucket(url: str) -> None:
    from api.utils.cloud.scw.bucket_utils import delete_object
    key = _extract_s3_key(url)
    delete_object("documents", key)


# ──────────────────────────────────────────────────────────────
# ViewSet
# ──────────────────────────────────────────────────────────────

class DocumentViewSet(viewsets.ModelViewSet):
    """
    CRUD complet des documents client + actions custom :

      GET    /documents/                        → liste (filtre ?client= ?document_type=)
      POST   /documents/                        → upload multi-fichiers
      GET    /documents/{id}/                   → détail
      PUT    /documents/{id}/                   → remplacement (fichier + métadonnées, nettoie S3)
      PATCH  /documents/{id}/                   → mise à jour partielle (idem)
      DELETE /documents/{id}/                   → suppression unitaire DB + S3
      GET    /documents/{id}/download/          → stream proxié depuis S3 (nom propre)
      DELETE /documents/bulk-delete/            → suppression multiple DB + S3
      GET    /documents/bulk-download/          → ZIP de plusieurs documents (?ids=1,2,3)
    """

    queryset         = Document.objects.select_related("client", "document_type")
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        client_id        = self.request.query_params.get("client")
        document_type_id = self.request.query_params.get("document_type")
        if client_id:
            qs = qs.filter(client_id=client_id)
        if document_type_id:
            qs = qs.filter(document_type_id=document_type_id)
        return qs

    # ──────────────────────────────────────────────
    # CREATE — upload multi-fichiers
    # ──────────────────────────────────────────────
    def create(self, request, *args, **kwargs):
        client_id        = request.data.get("client") or request.query_params.get("client")
        document_type_id = request.data.get("document_type")

        if not client_id:
            return Response({"detail": "client ID requis"}, status=400)

        from api.clients.models import Client
        try:
            client = Client.objects.get(pk=client_id)
        except Client.DoesNotExist:
            return Response({"detail": "Client inexistant"}, status=404)

        document_type = None
        if document_type_id:
            from api.document_types.models import DocumentType
            try:
                document_type = DocumentType.objects.get(pk=document_type_id)
            except DocumentType.DoesNotExist:
                return Response({"detail": "Type de document invalide"}, status=400)

        files = request.FILES.getlist("files") or [request.FILES.get("file")]
        files = [f for f in files if f]

        if not files:
            return Response({"detail": "Aucun fichier fourni"}, status=400)

        documents = []
        for index, file in enumerate(files):
            # _build_filename génère le nom définitif — store_client_document
            # doit l'utiliser tel quel, sans re-slugifier.
            filename = _build_filename(client, document_type, file.name, index)
            url      = store_client_document(client, file, filename)
            doc      = Document.objects.create(
                client=client,
                document_type=document_type,
                url=url,
            )
            documents.append(doc)

        serializer = self.get_serializer(documents, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # ──────────────────────────────────────────────
    # UPDATE / PARTIAL_UPDATE — nettoie l'ancien fichier S3
    # ──────────────────────────────────────────────
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        old_url  = instance.url

        # Si un nouveau fichier est fourni, on l'upload d'abord
        new_file = request.FILES.get("file")
        if new_file:
            document_type = instance.document_type
            type_id       = request.data.get("document_type")
            if type_id:
                from api.document_types.models import DocumentType
                try:
                    document_type = DocumentType.objects.get(pk=type_id)
                except DocumentType.DoesNotExist:
                    pass

            filename    = _build_filename(instance.client, document_type, new_file.name)
            new_url     = store_client_document(instance.client, new_file, filename)
            request.data["url"] = new_url  # injecte la nouvelle URL dans les data

        response = super().update(request, *args, **kwargs)

        # Supprime l'ancien fichier S3 si un nouveau a été uploadé
        if new_file and old_url:
            try:
                _delete_from_bucket(old_url)
            except Exception as e:
                print(f"Erreur suppression ancien fichier S3 : {e}")

        return response

    # ──────────────────────────────────────────────
    # DESTROY — suppression DB + bucket
    # ──────────────────────────────────────────────
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        file_url = instance.url

        if file_url:
            try:
                _delete_from_bucket(file_url)
            except Exception as e:
                print(f"Erreur suppression document du storage : {e}")

        return super().destroy(request, *args, **kwargs)

    # ──────────────────────────────────────────────
    # ACTION : téléchargement proxié unitaire
    # ──────────────────────────────────────────────
    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        """
        Streame le fichier S3 vers le client :
          - Content-Disposition: attachment  (force le téléchargement)
          - Nom de fichier propre : {client}_{type}.{ext}
          - L'URL pré-signée S3 n'est jamais exposée au navigateur
        """
        doc = self.get_object()

        if not doc.url:
            return Response({"detail": "Aucun fichier associé"}, status=404)

        from urllib.parse import unquote, urlparse
        original_name = unquote(urlparse(doc.url).path).split("/")[-1]
        filename      = _build_filename(doc.client, doc.document_type, original_name)

        try:
            s3_response = requests.get(doc.url, stream=True, timeout=30)
            s3_response.raise_for_status()
        except requests.RequestException as e:
            return Response({"detail": f"Erreur récupération fichier : {e}"}, status=502)

        content_type = s3_response.headers.get("Content-Type", "application/octet-stream")

        response = StreamingHttpResponse(
            s3_response.iter_content(chunk_size=8192),
            content_type=content_type,
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{filename.encode("utf-8").decode("ascii", errors="replace")}"; '
            f"filename*=UTF-8''{requests.utils.quote(filename)}"
        )
        content_length = s3_response.headers.get("Content-Length")
        if content_length:
            response["Content-Length"] = content_length

        return response

    # ──────────────────────────────────────────────
    # ACTION : suppression multiple DB + S3
    # ──────────────────────────────────────────────
    @action(detail=False, methods=["delete"], url_path="bulk-delete")
    def bulk_delete(self, request):
        """
        DELETE /documents/bulk-delete/
        Body JSON : { "ids": [1, 2, 3] }
        Supprime chaque document en DB et son fichier dans le bucket.
        Retourne 204 si tout OK, 207 si erreurs S3 partielles.
        """
        ids = request.data.get("ids", [])
        if not ids:
            return Response({"detail": "ids requis"}, status=400)

        documents = Document.objects.filter(pk__in=ids).select_related("client", "document_type")
        errors    = []

        for doc in documents:
            if doc.url:
                try:
                    _delete_from_bucket(doc.url)
                except Exception as e:
                    errors.append({"id": doc.pk, "error": str(e)})

        documents.delete()

        if errors:
            return Response(
                {"detail": "Supprimés avec erreurs S3", "errors": errors},
                status=status.HTTP_207_MULTI_STATUS,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ──────────────────────────────────────────────
    # ACTION : téléchargement ZIP multiple
    # ──────────────────────────────────────────────
    @action(detail=False, methods=["get"], url_path="bulk-download")
    def bulk_download(self, request):
        """
        GET /documents/bulk-download/?ids=1,2,3
        Retourne un fichier ZIP contenant tous les documents demandés.
        Les noms de fichiers dans le ZIP sont propres et sans collision.
        """
        ids_param = request.query_params.get("ids", "")
        ids       = [i for i in ids_param.split(",") if i.strip().isdigit()]

        if not ids:
            return Response({"detail": "ids requis (ex: ?ids=1,2,3)"}, status=400)

        documents = (
            Document.objects
            .filter(pk__in=ids)
            .select_related("client", "document_type")
        )

        buffer     = io.BytesIO()
        seen_names: dict[str, int] = {}

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for doc in documents:
                if not doc.url:
                    continue

                from urllib.parse import unquote, urlparse
                original_name = unquote(urlparse(doc.url).path).split("/")[-1]
                filename      = _build_filename(doc.client, doc.document_type, original_name)

                # Anti-collision : ajoute un suffixe si le nom existe déjà dans le ZIP
                count = seen_names.get(filename, 0)
                seen_names[filename] = count + 1
                if count:
                    base, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
                    filename  = f"{base}_{count}.{ext}" if ext else f"{base}_{count}"

                try:
                    s3_resp = requests.get(doc.url, timeout=30)
                    s3_resp.raise_for_status()
                    zf.writestr(filename, s3_resp.content)
                except requests.RequestException:
                    pass  # Fichier inaccessible ignoré silencieusement

        buffer.seek(0)
        response = StreamingHttpResponse(buffer, content_type="application/zip")
        response["Content-Disposition"] = 'attachment; filename="documents.zip"'
        return response