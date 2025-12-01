from decouple import config
from storages.backends.s3boto3 import S3Boto3Storage


class MinioAvatarStorage(S3Boto3Storage):
    bucket_name = config("BUCKET_USERS_AVATARS", default="users-avatars")
    location = ""
    file_overwrite = False


class MinioReceiptStorage(S3Boto3Storage):
    bucket_name = config("BUCKET_RECEIPTS", default="recus")
    location = ""
    file_overwrite = False


class MinioContractStorage(S3Boto3Storage):
    bucket_name = config("BUCKET_CONTRACTS", default="contracts")
    location = ""
    file_overwrite = False


class MinioDocumentStorage(S3Boto3Storage):
    bucket_name = config("BUCKET_CLIENT_DOCUMENTS", default="documents-clients")
    location = ""
    file_overwrite = False


class MinioInvoiceStorage(S3Boto3Storage):
    bucket_name = config("BUCKET_INVOICES", default="factures")
    location = ""
    file_overwrite = False