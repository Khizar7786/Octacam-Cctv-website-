from django.urls import path

from .views import (
    CsrfView, CustomerProfileView, LoginView, LogoutView, PasswordResetConfirmView,
    PasswordResetRequestView, RefreshView, RegisterView, StaffProfileView,
)


urlpatterns = [
    path("auth/csrf/", CsrfView.as_view(), name="auth-csrf"),
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/password-reset/request/", PasswordResetRequestView.as_view(), name="auth-password-reset-request"),
    path("auth/password-reset/confirm/", PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    path("account/profile/", CustomerProfileView.as_view(), name="account-profile"),
    path("staff/profile/", StaffProfileView.as_view(), name="staff-profile"),
]
