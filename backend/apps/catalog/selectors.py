from .models import Brand, Category, Product


def get_brands(*, include_inactive=False):
    queryset = Brand.objects.all()
    return queryset if include_inactive else queryset.filter(is_active=True)


def get_categories(*, include_inactive=False):
    queryset = Category.objects.all()
    return queryset if include_inactive else queryset.filter(is_active=True)


def get_staff_products():
    return Product.objects.select_related("brand", "category").all()
