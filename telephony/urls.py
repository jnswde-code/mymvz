from django.urls import path

from telephony import api, staff_views

app_name = "telephony"

urlpatterns = [
    # Only for the voice agent inside the Docker network (#14 section 7); the
    # public proxy must not forward /intern/ (#10).
    path("intern/telefon/auskunft/", api.practice_info, name="info"),
    path("intern/telefon/terminarten/", api.appointment_types, name="types"),
    path("intern/telefon/wunschzeit/", api.check_time_window, name="check_time_window"),
    path("intern/telefon/anfragen/", api.create_request, name="create_request"),
    path("intern/telefon/rueckrufe/", api.create_callback, name="create_callback"),
    path("intern/telefon/anrufe/", api.record_call, name="record_call"),
    # For the team (#45); the views are in their own file, like /anfragen/.
    path("rueckrufe/", staff_views.list_view, name="callbacks"),
    path("rueckrufe/<uuid:pk>/erledigt/", staff_views.done_view, name="callback_done"),
]
