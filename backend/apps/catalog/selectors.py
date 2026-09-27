from django.db.models import Prefetch

from .models import Brand, Category, Product, ProductSpecificationValue, SpecificationChoice, SpecificationDefinition


def get_brands(*, include_inactive=False):
    queryset = Brand.objects.all()
    return queryset if include_inactive else queryset.filter(is_active=True)


def get_categories(*, include_inactive=False):
    queryset = Category.objects.all()
    return queryset if include_inactive else queryset.filter(is_active=True)


def get_staff_products():
    values = ProductSpecificationValue.objects.select_related("definition", "choice")
    return Product.objects.select_related("brand", "category").prefetch_related(
        Prefetch("specification_values", queryset=values),
    )


def get_public_products():
    return Product.objects.select_related("brand", "category").filter(
        is_published=True,
        brand__is_active=True,
        category__is_active=True,
    )


def get_public_product_details():
    values = ProductSpecificationValue.objects.select_related("definition", "choice").filter(
        definition__is_active=True,
        definition__is_displayed=True,
    )
    return get_public_products().prefetch_related(Prefetch("specification_values", queryset=values))


def get_specification_definitions(*, category_id, include_inactive=False):
    queryset = SpecificationDefinition.objects.filter(category_id=category_id).prefetch_related(
        Prefetch("choices", queryset=SpecificationChoice.objects.all()),
    )
    return queryset if include_inactive else queryset.filter(is_active=True)


def get_specification_choices(*, include_inactive=False):
    queryset = SpecificationChoice.objects.select_related("definition")
    return queryset if include_inactive else queryset.filter(is_active=True)
