from rest_framework.permissions import BasePermission


class IsCustomer(BasePermission):
    message = "Customer access is required."

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.is_active and not request.user.is_staff
        )


class IsStaff(BasePermission):
    message = "Staff access is required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active and request.user.is_staff)
