from rest_framework.pagination import PageNumberPagination


class CRMLeadPagination(PageNumberPagination):
    """
    Pagination optimisée pour le CRM.
    """

    page_size = 7
    page_size_query_param = "page_size"
    max_page_size = 50