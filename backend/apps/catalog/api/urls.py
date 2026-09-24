from django.urls import path

from . import views


urlpatterns = [
    path("catalog/brands/", views.PublicBrandList.as_view(), name="public-brands"),
    path("catalog/brands/<slug:slug>/", views.PublicBrandDetail.as_view(), name="public-brand"),
    path("catalog/categories/", views.PublicCategoryList.as_view(), name="public-categories"),
    path("catalog/categories/<slug:slug>/", views.PublicCategoryDetail.as_view(), name="public-category"),
    path("staff/catalog/brands/", views.StaffBrandList.as_view(), name="staff-brands"),
    path("staff/catalog/brands/<int:pk>/", views.StaffBrandUpdate.as_view(), name="staff-brand"),
    path("staff/catalog/categories/", views.StaffCategoryList.as_view(), name="staff-categories"),
    path("staff/catalog/categories/<int:pk>/", views.StaffCategoryUpdate.as_view(), name="staff-category"),
    path("staff/catalog/products/", views.StaffProductList.as_view(), name="staff-products"),
    path("staff/catalog/products/<int:pk>/", views.StaffProductDetail.as_view(), name="staff-product"),
]
