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
]
