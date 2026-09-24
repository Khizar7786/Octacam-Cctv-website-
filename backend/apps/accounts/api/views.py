from django.conf import settings
from django.contrib.auth import authenticate
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.serializers import (
    ApiErrorSerializer,
    AuthResponseSerializer,
    LoginSerializer,
    RegistrationSerializer,
    UserSerializer,
)
from apps.accounts.services import issue_tokens, revoke_refresh, rotate_refresh
from apps.core.exceptions import AuthenticationError
from apps.core.permissions import IsCustomer, IsStaff


CSRF_HEADER = OpenApiParameter(
    name="X-CSRFToken", type=str, location=OpenApiParameter.HEADER, required=True,
    description="Token returned by GET /api/v1/auth/csrf/.",
)
REFRESH_COOKIE = OpenApiParameter(
    name="octacam_refresh", type=str, location=OpenApiParameter.COOKIE, required=True,
    description="HttpOnly refresh cookie set on registration, login, or refresh.",
)


def set_refresh_cookie(response, token):
    response.set_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        token,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        secure=settings.AUTH_REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite="Lax",
    )


def clear_refresh_cookie(response):
    response.delete_cookie(settings.AUTH_REFRESH_COOKIE_NAME, path=settings.AUTH_REFRESH_COOKIE_PATH, samesite="Lax")


def auth_response(user, status_code):
    access, refresh = issue_tokens(user)
    response = Response({"user": UserSerializer(user).data, "access": access}, status=status_code)
    set_refresh_cookie(response, refresh)
    return response


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["auth"], responses={200: {"type": "object", "properties": {"csrfToken": {"type": "string"}}}})
    def get(self, request):
        return Response({"csrfToken": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "auth_register"

    @extend_schema(
        tags=["auth"], request=RegistrationSerializer, parameters=[CSRF_HEADER],
        responses={
            201: AuthResponseSerializer,
            400: ApiErrorSerializer,
            403: ApiErrorSerializer,
            429: ApiErrorSerializer,
        },
    )
    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return auth_response(user, status.HTTP_201_CREATED)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "auth_login"

    @extend_schema(
        tags=["auth"], request=LoginSerializer, parameters=[CSRF_HEADER],
        responses={200: AuthResponseSerializer, 400: ApiErrorSerializer, 401: ApiErrorSerializer,
                   403: ApiErrorSerializer, 429: ApiErrorSerializer},
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request=request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            raise AuthenticationError("Invalid email or password.")
        return auth_response(user, status.HTTP_200_OK)


@method_decorator(csrf_protect, name="dispatch")
class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "auth_refresh"

    @extend_schema(
        tags=["auth"], request=None, parameters=[CSRF_HEADER, REFRESH_COOKIE],
        responses={200: AuthResponseSerializer, 401: ApiErrorSerializer, 403: ApiErrorSerializer,
                   429: ApiErrorSerializer},
    )
    def post(self, request):
        raw_token = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
        if not raw_token:
            raise AuthenticationError("Refresh token is missing.")
        user, access, refresh = rotate_refresh(raw_token)
        response = Response({"user": UserSerializer(user).data, "access": access})
        set_refresh_cookie(response, refresh)
        return response


@method_decorator(csrf_protect, name="dispatch")
class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["auth"], request=None, parameters=[CSRF_HEADER, REFRESH_COOKIE],
        responses={204: OpenApiResponse(description="Refresh cookie cleared."), 403: ApiErrorSerializer},
    )
    def post(self, request):
        raw_token = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
        if raw_token:
            revoke_refresh(raw_token)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response


class CustomerProfileView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(tags=["account"], responses={200: UserSerializer, 401: ApiErrorSerializer, 403: ApiErrorSerializer})
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class StaffProfileView(APIView):
    permission_classes = [IsStaff]

    @extend_schema(tags=["staff"], responses={200: UserSerializer, 401: ApiErrorSerializer, 403: ApiErrorSerializer})
    def get(self, request):
        return Response(UserSerializer(request.user).data)
