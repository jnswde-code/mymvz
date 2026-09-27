from django.urls import path

from appointments import staff_views

app_name = "appointments_staff"

urlpatterns = [
    path("anfragen/", staff_views.list_view, name="list"),
    path("anfragen/<uuid:pk>/", staff_views.detail_view, name="detail"),
    path("anfragen/<uuid:pk>/bestaetigen/", staff_views.confirm_view, name="confirm"),
    path("anfragen/<uuid:pk>/vorschlagen/", staff_views.propose_view, name="propose"),
    path("anfragen/<uuid:pk>/ablehnen/", staff_views.decline_view, name="decline"),
    path("anfragen/<uuid:pk>/notiz/", staff_views.note_view, name="note"),
]
