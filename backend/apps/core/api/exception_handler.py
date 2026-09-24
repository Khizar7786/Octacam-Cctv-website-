from django.http import JsonResponse
from rest_framework import status
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    if response.status_code == status.HTTP_400_BAD_REQUEST:
        fields = {
            key: [str(value) for value in values] if isinstance(values, list) else [str(values)]
            for key, values in response.data.items()
        } if isinstance(response.data, dict) else {}
        code = "VALIDATION_ERROR"
        message = "Some fields need attention."
    else:
        fields = {}
        code = {
            401: "AUTHENTICATION_REQUIRED",
            403: "PERMISSION_DENIED",
            404: "NOT_FOUND",
            429: "RATE_LIMITED",
        }.get(response.status_code, "REQUEST_ERROR")
        detail = response.data.get("detail") if isinstance(response.data, dict) else None
        message = str(detail or "The request could not be completed.")

    response.data = {"error": {"code": code, "message": message, "fields": fields}}
    return response


def csrf_failure(request, reason=""):
    return JsonResponse(
        {"error": {"code": "PERMISSION_DENIED", "message": "CSRF verification failed.", "fields": {}}},
        status=403,
    )
