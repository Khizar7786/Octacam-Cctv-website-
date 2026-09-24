from django.conf import settings
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny

from apps.accounts.api.serializers import ApiErrorSerializer
from apps.catalog.selectors import get_brands, get_categories, get_staff_products
from apps.core.permissions import IsStaff

from .serializers import BrandSerializer, CategorySerializer, ProductDraftSerializer


class CatalogPagination(PageNumberPagination):
    page_size = settings.CATALOG_PAGE_SIZE


class PublicTaxonomyList(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = CatalogPagination


class PublicTaxonomyDetail(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    lookup_field = "slug"


class PublicBrandList(PublicTaxonomyList):
    serializer_class = BrandSerializer

    def get_queryset(self):
        return get_brands()


@extend_schema_view(get=extend_schema(responses={200: BrandSerializer, 404: ApiErrorSerializer}))
class PublicBrandDetail(PublicTaxonomyDetail):
    serializer_class = BrandSerializer

    def get_queryset(self):
        return get_brands()


class PublicCategoryList(PublicTaxonomyList):
    serializer_class = CategorySerializer

    def get_queryset(self):
        return get_categories()


@extend_schema_view(get=extend_schema(responses={200: CategorySerializer, 404: ApiErrorSerializer}))
class PublicCategoryDetail(PublicTaxonomyDetail):
    serializer_class = CategorySerializer

    def get_queryset(self):
        return get_categories()


class StaffTaxonomyList(generics.ListCreateAPIView):
    permission_classes = [IsStaff]
    pagination_class = CatalogPagination


class StaffTaxonomyUpdate(generics.UpdateAPIView):
    permission_classes = [IsStaff]
    http_method_names = ["patch", "options"]


@extend_schema_view(
    get=extend_schema(responses={200: BrandSerializer(many=True), 401: ApiErrorSerializer, 403: ApiErrorSerializer}),
    post=extend_schema(responses={201: BrandSerializer, 400: ApiErrorSerializer,
                                  401: ApiErrorSerializer, 403: ApiErrorSerializer}),
)
class StaffBrandList(StaffTaxonomyList):
    serializer_class = BrandSerializer

    def get_queryset(self):
        return get_brands(include_inactive=True)


@extend_schema_view(patch=extend_schema(responses={
    200: BrandSerializer, 400: ApiErrorSerializer, 401: ApiErrorSerializer,
    403: ApiErrorSerializer, 404: ApiErrorSerializer,
}))
class StaffBrandUpdate(StaffTaxonomyUpdate):
    serializer_class = BrandSerializer

    def get_queryset(self):
        return get_brands(include_inactive=True)


@extend_schema_view(
    get=extend_schema(responses={200: CategorySerializer(many=True), 401: ApiErrorSerializer, 403: ApiErrorSerializer}),
    post=extend_schema(responses={201: CategorySerializer, 400: ApiErrorSerializer,
                                  401: ApiErrorSerializer, 403: ApiErrorSerializer}),
)
class StaffCategoryList(StaffTaxonomyList):
    serializer_class = CategorySerializer

    def get_queryset(self):
        return get_categories(include_inactive=True)


@extend_schema_view(patch=extend_schema(responses={
    200: CategorySerializer, 400: ApiErrorSerializer, 401: ApiErrorSerializer,
    403: ApiErrorSerializer, 404: ApiErrorSerializer,
}))
class StaffCategoryUpdate(StaffTaxonomyUpdate):
    serializer_class = CategorySerializer

    def get_queryset(self):
        return get_categories(include_inactive=True)


@extend_schema_view(
    get=extend_schema(responses={200: ProductDraftSerializer(many=True),
                                 401: ApiErrorSerializer, 403: ApiErrorSerializer}),
    post=extend_schema(responses={201: ProductDraftSerializer, 400: ApiErrorSerializer,
                                  401: ApiErrorSerializer, 403: ApiErrorSerializer}),
)
class StaffProductList(generics.ListCreateAPIView):
    permission_classes = [IsStaff]
    serializer_class = ProductDraftSerializer
    pagination_class = CatalogPagination

    def get_queryset(self):
        return get_staff_products()


@extend_schema_view(
    get=extend_schema(responses={200: ProductDraftSerializer, 401: ApiErrorSerializer,
                                 403: ApiErrorSerializer, 404: ApiErrorSerializer}),
    patch=extend_schema(responses={200: ProductDraftSerializer, 400: ApiErrorSerializer,
                                   401: ApiErrorSerializer, 403: ApiErrorSerializer, 404: ApiErrorSerializer}),
)
class StaffProductDetail(generics.RetrieveUpdateAPIView):
    permission_classes = [IsStaff]
    serializer_class = ProductDraftSerializer
    http_method_names = ["get", "patch", "options"]

    def get_queryset(self):
        return get_staff_products()
