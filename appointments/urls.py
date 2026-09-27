from django.urls import path

from appointments import views

app_name = "appointments"

urlpatterns = [
    path("termin/", views.request_form, name="request"),
    path("termin/gesendet/", views.request_sent, name="sent"),
    path("termin/datenschutz/", views.privacy_notice, name="privacy"),
    path("termin/link/<str:token>/", views.link, name="link"),
]
