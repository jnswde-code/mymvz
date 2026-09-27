from django.urls import path

from telephony import api

app_name = "telephony"

# Only for the voice agent inside the Docker network (#14 section 7); the
# public proxy must not forward /intern/ (#10).
urlpatterns = [
    path("intern/telefon/auskunft/", api.practice_info, name="info"),
    path("intern/telefon/terminarten/", api.appointment_types, name="types"),
    path("intern/telefon/wunschzeit/", api.check_time_window, name="check_time_window"),
    path("intern/telefon/anfragen/", api.create_request, name="create_request"),
]
