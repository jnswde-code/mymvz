from django.urls import path

from patients import views

app_name = "patients"

urlpatterns = [
    path("patienten/", views.search_view, name="search"),
    path("patienten/neu/", views.create_view, name="create"),
    path("patienten/<uuid:pk>/", views.detail_view, name="detail"),
    path("patienten/<uuid:pk>/bearbeiten/", views.edit_view, name="edit"),
    path("patienten/<uuid:pk>/kennungen/", views.add_identifier_view, name="add_identifier"),
    path(
        "patienten/<uuid:pk>/kennungen/<uuid:identifier_pk>/beenden/",
        views.end_identifier_view,
        name="end_identifier",
    ),
    path("patienten/<uuid:pk>/team/", views.add_care_team_view, name="add_care_team"),
    path(
        "patienten/<uuid:pk>/team/<uuid:member_pk>/beenden/",
        views.end_care_team_view,
        name="end_care_team",
    ),
    path("patienten/<uuid:pk>/freigaben/", views.add_consent_view, name="add_consent"),
    path(
        "patienten/<uuid:pk>/freigaben/<uuid:consent_pk>/beenden/",
        views.end_consent_view,
        name="end_consent",
    ),
    path("patienten/<uuid:pk>/sperrvermerk/", views.restrict_view, name="restrict"),
    path(
        "patienten/<uuid:pk>/sperrvermerk/aufheben/",
        views.lift_restriction_view,
        name="lift_restriction",
    ),
    path("patienten/<uuid:pk>/konto/", views.link_account_view, name="link_account"),
    path("patienten/<uuid:pk>/konto/entfernen/", views.unlink_account_view, name="unlink_account"),
    path("patienten/<uuid:pk>/notfall/", views.emergency_view, name="emergency"),
]
