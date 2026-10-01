"""Seitenweise Listen (?page=): 50 je Seite, mit ?seitengroesse= bis 2000 (z. B. alle Gewichte für den Verlauf)."""
from rest_framework.pagination import PageNumberPagination


class Seiten(PageNumberPagination):
    page_size = 50
    page_size_query_param = "seitengroesse"
    max_page_size = 2000
