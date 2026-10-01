from django.urls import path

from .views import (
    PublicSurveySlotList, StaffSurveySlotDetail, StaffSurveySlotList,
    SurveyBookingCreateView, GuestSurveyTrackingView,
    StaffSurveyBookingList, StaffSurveyBookingDetail, StaffSurveyBookingHistory,
    StaffSurveyReschedule, StaffSurveyTransition, StaffSurveyNotes,
)


urlpatterns = [
    path("surveys/slots/", PublicSurveySlotList.as_view(), name="public-survey-slots"),
    path("surveys/bookings/", SurveyBookingCreateView.as_view(), name="survey-booking-create"),
    path("surveys/track/<str:signed_token>/", GuestSurveyTrackingView.as_view(), name="guest-survey-track"),
    path("staff/surveys/slots/", StaffSurveySlotList.as_view(), name="staff-survey-slots"),
    path("staff/surveys/slots/<uuid:public_id>/", StaffSurveySlotDetail.as_view(), name="staff-survey-slot"),
    path("staff/surveys/bookings/", StaffSurveyBookingList.as_view(), name="staff-survey-bookings"),
    path("staff/surveys/bookings/<uuid:public_id>/", StaffSurveyBookingDetail.as_view(), name="staff-survey-booking"),
    path("staff/surveys/bookings/<uuid:public_id>/history/", StaffSurveyBookingHistory.as_view(), name="staff-survey-booking-history"),
    path("staff/surveys/bookings/<uuid:public_id>/reschedule/", StaffSurveyReschedule.as_view(), name="staff-survey-reschedule"),
    path("staff/surveys/bookings/<uuid:public_id>/transition/", StaffSurveyTransition.as_view(), name="staff-survey-transition"),
    path("staff/surveys/bookings/<uuid:public_id>/notes/", StaffSurveyNotes.as_view(), name="staff-survey-notes"),
]
