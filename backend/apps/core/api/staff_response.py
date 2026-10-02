from drf_spectacular.utils import OpenApiParameter


PRIVATE_STAFF_HEADERS = [
    OpenApiParameter("Cache-Control", location=OpenApiParameter.HEADER, response=True,
                     description="private, no-store"),
    OpenApiParameter("Referrer-Policy", location=OpenApiParameter.HEADER, response=True,
                     description="no-referrer"),
    OpenApiParameter("X-Robots-Tag", location=OpenApiParameter.HEADER, response=True,
                     description="noindex, nofollow"),
]


class PrivateStaffResponseMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        response["Referrer-Policy"] = "no-referrer"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response
