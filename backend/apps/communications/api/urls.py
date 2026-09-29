from django.urls import path

from .views import StaffEmailList, StaffEmailRetry


urlpatterns = [
    path("staff/communications/emails/", StaffEmailList.as_view(), name="staff-emails"),
    path("staff/communications/emails/<int:email_id>/retry/", StaffEmailRetry.as_view(), name="staff-email-retry"),
]
