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
    path("anfragen/<uuid:pk>/patient/", staff_views.assign_view, name="assign"),
    path("anfragen/<uuid:pk>/patient/aufheben/", staff_views.unassign_view, name="unassign"),
    path("anfragen/termine/", staff_views.appointment_list_view, name="appointments"),
    path(
        "anfragen/<uuid:pk>/termine/<uuid:appointment_pk>/absagen/",
        staff_views.cancel_view,
        name="cancel",
    ),
    path(
        "anfragen/<uuid:pk>/termine/<uuid:appointment_pk>/absage-telefon/",
        staff_views.phone_cancel_view,
        name="phone_cancel",
    ),
    path(
        "anfragen/<uuid:pk>/termine/<uuid:appointment_pk>/zurueckziehen/",
        staff_views.withdraw_view,
        name="withdraw",
    ),
    path(
        "anfragen/<uuid:pk>/termine/<uuid:appointment_pk>/eingetragen/",
        staff_views.entered_view,
        name="entered",
    ),
    path(
        "anfragen/<uuid:pk>/termine/<uuid:appointment_pk>/ausgetragen/",
        staff_views.removed_view,
        name="removed",
    ),
]
