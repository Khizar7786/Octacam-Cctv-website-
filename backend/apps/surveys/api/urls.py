from django.urls import path

from .views import PublicSurveySlotList, StaffSurveySlotDetail, StaffSurveySlotList


urlpatterns = [
    path("surveys/slots/", PublicSurveySlotList.as_view(), name="public-survey-slots"),
    path("staff/surveys/slots/", StaffSurveySlotList.as_view(), name="staff-survey-slots"),
    path("staff/surveys/slots/<uuid:public_id>/", StaffSurveySlotDetail.as_view(), name="staff-survey-slot"),
]
