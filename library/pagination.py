from rest_framework.pagination import PageNumberPagination

class DefaultPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param= "page_zise"
    max_page_size = 100
    page_query_param="page"