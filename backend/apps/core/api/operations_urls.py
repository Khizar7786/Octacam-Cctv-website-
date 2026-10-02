from django.urls import path

from .operations_views import StaffActivityList, StaffOverview


urlpatterns = [
    path("staff/overview/", StaffOverview.as_view(), name="staff-overview"),
    path("staff/activity/", StaffActivityList.as_view(), name="staff-activity"),
]
