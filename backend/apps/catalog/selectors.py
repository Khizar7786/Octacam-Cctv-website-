from django.db.models import Case, DecimalField, Exists, IntegerField, Max, Min, OuterRef, Prefetch, Q, Value, When
from django.db.models.functions import Coalesce

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
        "images",
    )


def get_public_products():
    return Product.objects.select_related("brand", "category").prefetch_related("images").filter(
        is_published=True,
        brand__is_active=True,
        category__is_active=True,
    )


def public_product_query(filters, specification_filters=(), *, order=True):
    queryset = get_public_products()
    if filters.get("brand"):
        queryset = queryset.filter(brand__slug=filters["brand"])
    if filters.get("category"):
        queryset = queryset.filter(category__slug=filters["category"])
    if filters.get("availability") == "in_stock":
        queryset = queryset.filter(stock_quantity__gt=0)
    elif filters.get("availability") == "out_of_stock":
        queryset = queryset.filter(stock_quantity=0)
    queryset = queryset.annotate(_selling_price=Coalesce(
        "sale_price", "regular_price", output_field=DecimalField(max_digits=12, decimal_places=2),
    ))
    if filters.get("min_price") is not None:
        queryset = queryset.filter(_selling_price__gte=filters["min_price"])
    if filters.get("max_price") is not None:
        queryset = queryset.filter(_selling_price__lte=filters["max_price"])
    query = filters.get("q")
    if query:
        queryset = queryset.filter(Q(name__icontains=query) | Q(sku__icontains=query))
    for index, (definition, lookup, value) in enumerate(specification_filters):
        matching = ProductSpecificationValue.objects.filter(
            product_id=OuterRef("pk"), definition_id=definition.pk, **{lookup: value},
        )
        queryset = queryset.alias(**{f"_spec_match_{index}": Exists(matching)}).filter(
            **{f"_spec_match_{index}": True},
        )
    if not order:
        return queryset.order_by()
    sort = filters.get("sort", "relevance")
    if sort == "price_asc":
        return queryset.order_by("_selling_price", "id")
    if sort == "price_desc":
        return queryset.order_by("-_selling_price", "id")
    if query:
        queryset = queryset.annotate(_relevance=Case(
            When(sku__iexact=query, then=Value(0)),
            When(sku__istartswith=query, then=Value(1)),
            When(name__istartswith=query, then=Value(2)),
            When(sku__icontains=query, then=Value(3)),
            default=Value(4), output_field=IntegerField(),
        ))
        return queryset.order_by("_relevance", "name", "id")
    return queryset.order_by("name", "id")


def public_filter_metadata(filters):
    category = filters.get("category")
    brand = filters.get("brand")
    brand_scope = public_product_query({"category": category}, order=False)
    category_scope = public_product_query({"brand": brand}, order=False)
    scoped = public_product_query(filters, order=False)
    brands = Brand.objects.filter(is_active=True, products__in=brand_scope).distinct().order_by("sort_order", "name", "id")
    categories = Category.objects.filter(is_active=True, products__in=category_scope).distinct().order_by("sort_order", "name", "id")
    price = scoped.aggregate(min=Min("_selling_price"), max=Max("_selling_price"))
    specifications = []
    if category:
        definitions = SpecificationDefinition.objects.filter(
            category__slug=category, category__is_active=True, is_active=True, is_filterable=True,
        ).order_by("sort_order", "label", "id")
        values = ProductSpecificationValue.objects.filter(product__in=scoped)
        for definition in definitions:
            matching = values.filter(definition=definition)
            base = {"key": definition.key, "label": definition.label, "unit": definition.unit}
            if definition.data_type == SpecificationDefinition.DataType.CHOICE:
                choices = SpecificationChoice.objects.filter(
                    definition=definition, is_active=True, product_values__in=matching,
                ).distinct().order_by("sort_order", "label", "id")
                options = [
                    {"value": choice.value, "label": choice.label} for choice in choices
                ]
                if options:
                    specifications.append({**base, "type": "choice", "options": options})
            elif definition.data_type == SpecificationDefinition.DataType.BOOLEAN:
                present = set(matching.values_list("boolean_value", flat=True).distinct())
                options = [
                    {"value": value, "label": "Yes" if value else "No"}
                    for value in (True, False) if value in present
                ]
                if options:
                    specifications.append({**base, "type": "boolean", "options": options})
            elif definition.data_type in (SpecificationDefinition.DataType.INTEGER, SpecificationDefinition.DataType.DECIMAL):
                field = "integer_value" if definition.data_type == SpecificationDefinition.DataType.INTEGER else "decimal_value"
                bounds = matching.aggregate(min=Min(field), max=Max(field))
                if bounds["min"] is not None:
                    specifications.append({**base, "type": f"{definition.data_type}_range",
                                           "min": str(bounds["min"]), "max": str(bounds["max"])})
    return {
        "brand": [{"value": item.slug, "label": item.name} for item in brands],
        "category": [{"value": item.slug, "label": item.name} for item in categories],
        "price": {key: str(value) if value is not None else None for key, value in price.items()},
        "specifications": specifications,
    }


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
