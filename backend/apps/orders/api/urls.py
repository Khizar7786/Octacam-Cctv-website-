from django.urls import path

from .views import (
    CheckoutPlaceView, CheckoutQuoteView, CustomerOrderDetailView,
    CustomerOrderListView, GuestOrderTrackingView,
)


urlpatterns = [
    path("checkout/quote/", CheckoutQuoteView.as_view(), name="checkout-quote"),
    path("checkout/place/", CheckoutPlaceView.as_view(), name="checkout-place"),
    path("orders/track/<str:signed_token>/", GuestOrderTrackingView.as_view(), name="guest-order-track"),
    path("account/orders/", CustomerOrderListView.as_view(), name="account-orders"),
    path("account/orders/<uuid:public_id>/", CustomerOrderDetailView.as_view(), name="account-order-detail"),
]
