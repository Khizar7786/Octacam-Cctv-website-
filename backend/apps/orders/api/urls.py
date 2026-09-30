from django.urls import path

from .views import (
    CheckoutPlaceView, CheckoutQuoteView, CustomerOrderDetailView,
    CustomerOrderListView, GuestOrderTrackingView, StaffOrderCodCollectedView,
    StaffOrderCourierView, StaffOrderDetailView, StaffOrderHistoryView,
    StaffOrderListView, StaffOrderTransitionView,
)


urlpatterns = [
    path("checkout/quote/", CheckoutQuoteView.as_view(), name="checkout-quote"),
    path("checkout/place/", CheckoutPlaceView.as_view(), name="checkout-place"),
    path("orders/track/<str:signed_token>/", GuestOrderTrackingView.as_view(), name="guest-order-track"),
    path("account/orders/", CustomerOrderListView.as_view(), name="account-orders"),
    path("account/orders/<uuid:public_id>/", CustomerOrderDetailView.as_view(), name="account-order-detail"),
    path("staff/orders/", StaffOrderListView.as_view(), name="staff-order-list"),
    path("staff/orders/<uuid:public_id>/", StaffOrderDetailView.as_view(), name="staff-order-detail"),
    path("staff/orders/<uuid:public_id>/history/", StaffOrderHistoryView.as_view(), name="staff-order-history"),
    path("staff/orders/<uuid:public_id>/transition/", StaffOrderTransitionView.as_view(), name="staff-order-transition"),
    path("staff/orders/<uuid:public_id>/courier/", StaffOrderCourierView.as_view(), name="staff-order-courier"),
    path("staff/orders/<uuid:public_id>/mark-cod-collected/", StaffOrderCodCollectedView.as_view(), name="staff-order-cod-collected"),
]
