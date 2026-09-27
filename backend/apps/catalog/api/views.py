from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny

from apps.accounts.api.serializers import ApiErrorSerializer
from apps.catalog.models import SpecificationDefinition
from apps.catalog.selectors import (
    get_brands,
    get_categories,
    get_public_product_details,
    get_public_products,
    get_specification_choices,
    get_specification_definitions,
    get_staff_products,
)
from apps.core.permissions import IsStaff

from .serializers import (
    BrandSerializer,
    CategorySerializer,
    ProductStaffSerializer,
    PublicProductDetailSerializer,
    PublicProductListSerializer,
    SpecificationChoiceSerializer,
    SpecificationDefinitionSerializer,
)


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


class PublicProductList(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PublicProductListSerializer
    pagination_class = CatalogPagination

    def get_queryset(self):
        return get_public_products()


@extend_schema_view(get=extend_schema(responses={200: PublicProductDetailSerializer, 404: ApiErrorSerializer}))
class PublicProductDetail(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PublicProductDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return get_public_product_details()


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
    get=extend_schema(responses={
        200: SpecificationDefinitionSerializer(many=True),
        401: ApiErrorSerializer,
        403: ApiErrorSerializer,
        404: ApiErrorSerializer,
    }),
    post=extend_schema(responses={
        201: SpecificationDefinitionSerializer,
        400: ApiErrorSerializer,
        401: ApiErrorSerializer,
        403: ApiErrorSerializer,
        404: ApiErrorSerializer,
    }),
)
class StaffCategorySpecificationList(generics.ListCreateAPIView):
    permission_classes = [IsStaff]
    serializer_class = SpecificationDefinitionSerializer

    def get_category(self):
        if not hasattr(self, "_category"):
            self._category = get_object_or_404(
                get_categories(include_inactive=True),
                pk=self.kwargs["category_pk"],
            )
        return self._category

    def get_queryset(self):
        return get_specification_definitions(category_id=self.get_category().pk, include_inactive=True)

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "category": self.get_category()}


@extend_schema_view(patch=extend_schema(responses={
    200: SpecificationDefinitionSerializer,
    400: ApiErrorSerializer,
    401: ApiErrorSerializer,
    403: ApiErrorSerializer,
    404: ApiErrorSerializer,
}))
class StaffSpecificationUpdate(generics.UpdateAPIView):
    permission_classes = [IsStaff]
    serializer_class = SpecificationDefinitionSerializer
    http_method_names = ["patch", "options"]

    def get_queryset(self):
        return SpecificationDefinition.objects.prefetch_related("choices")


@extend_schema_view(post=extend_schema(responses={
    201: SpecificationChoiceSerializer,
    400: ApiErrorSerializer,
    401: ApiErrorSerializer,
    403: ApiErrorSerializer,
    404: ApiErrorSerializer,
}))
class StaffSpecificationChoiceCreate(generics.CreateAPIView):
    permission_classes = [IsStaff]
    serializer_class = SpecificationChoiceSerializer

    def get_definition(self):
        if not hasattr(self, "_definition"):
            self._definition = get_object_or_404(SpecificationDefinition, pk=self.kwargs["definition_pk"])
        return self._definition

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "definition": self.get_definition()}


@extend_schema_view(patch=extend_schema(responses={
    200: SpecificationChoiceSerializer,
    400: ApiErrorSerializer,
    401: ApiErrorSerializer,
    403: ApiErrorSerializer,
    404: ApiErrorSerializer,
}))
class StaffSpecificationChoiceUpdate(generics.UpdateAPIView):
    permission_classes = [IsStaff]
    serializer_class = SpecificationChoiceSerializer
    http_method_names = ["patch", "options"]

    def get_queryset(self):
        return get_specification_choices(include_inactive=True)


@extend_schema_view(
    get=extend_schema(responses={200: ProductStaffSerializer(many=True),
                                 401: ApiErrorSerializer, 403: ApiErrorSerializer}),
    post=extend_schema(responses={201: ProductStaffSerializer, 400: ApiErrorSerializer,
                                  401: ApiErrorSerializer, 403: ApiErrorSerializer}),
)
class StaffProductList(generics.ListCreateAPIView):
    permission_classes = [IsStaff]
    serializer_class = ProductStaffSerializer
    pagination_class = CatalogPagination

    def get_queryset(self):
        return get_staff_products()


@extend_schema_view(
    get=extend_schema(responses={200: ProductStaffSerializer, 401: ApiErrorSerializer,
                                 403: ApiErrorSerializer, 404: ApiErrorSerializer}),
    patch=extend_schema(responses={200: ProductStaffSerializer, 400: ApiErrorSerializer,
                                   401: ApiErrorSerializer, 403: ApiErrorSerializer, 404: ApiErrorSerializer}),
)
class StaffProductDetail(generics.RetrieveUpdateAPIView):
    permission_classes = [IsStaff]
    serializer_class = ProductStaffSerializer
    http_method_names = ["get", "patch", "options"]

    def get_queryset(self):
        return get_staff_products()
