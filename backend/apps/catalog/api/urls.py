from django.urls import path

from . import views


urlpatterns = [
    path("catalog/brands/", views.PublicBrandList.as_view(), name="public-brands"),
    path("catalog/brands/<slug:slug>/", views.PublicBrandDetail.as_view(), name="public-brand"),
    path("catalog/categories/", views.PublicCategoryList.as_view(), name="public-categories"),
    path("catalog/categories/<slug:slug>/", views.PublicCategoryDetail.as_view(), name="public-category"),
    path("catalog/products/", views.PublicProductList.as_view(), name="public-products"),
    path("catalog/filters/", views.PublicFilterMetadata.as_view(), name="public-filters"),
    path("catalog/products/<slug:slug>/", views.PublicProductDetail.as_view(), name="public-product"),
    path("staff/catalog/brands/", views.StaffBrandList.as_view(), name="staff-brands"),
    path("staff/catalog/brands/<int:pk>/", views.StaffBrandUpdate.as_view(), name="staff-brand"),
    path("staff/catalog/categories/", views.StaffCategoryList.as_view(), name="staff-categories"),
    path("staff/catalog/categories/<int:pk>/", views.StaffCategoryUpdate.as_view(), name="staff-category"),
    path(
        "staff/catalog/categories/<int:category_pk>/specifications/",
        views.StaffCategorySpecificationList.as_view(),
        name="staff-category-specifications",
    ),
    path(
        "staff/catalog/specifications/<int:pk>/",
        views.StaffSpecificationUpdate.as_view(),
        name="staff-specification",
    ),
    path(
        "staff/catalog/specifications/<int:definition_pk>/choices/",
        views.StaffSpecificationChoiceCreate.as_view(),
        name="staff-specification-choices",
    ),
    path(
        "staff/catalog/specification-choices/<int:pk>/",
        views.StaffSpecificationChoiceUpdate.as_view(),
        name="staff-specification-choice",
    ),
    path("staff/catalog/products/", views.StaffProductList.as_view(), name="staff-products"),
    path("staff/catalog/products/<int:pk>/", views.StaffProductDetail.as_view(), name="staff-product"),
    path("staff/catalog/products/<int:product_pk>/stock-adjustments/", views.StaffProductStockAdjustments.as_view(), name="staff-product-stock-adjustments"),
    path("staff/catalog/products/<int:product_pk>/images/", views.StaffProductImageCreate.as_view(), name="staff-product-images"),
    path("staff/catalog/product-images/<int:pk>/", views.StaffProductImageDetail.as_view(), name="staff-product-image"),
]
