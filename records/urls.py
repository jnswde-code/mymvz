from django.urls import path, register_converter

from records import views


class KindConverter:
    """`kontakte` or `eintraege`, the keys of `views.KINDS`; anything else is 404."""

    regex = "|".join(views.KINDS)

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


register_converter(KindConverter, "kind")

app_name = "records"

urlpatterns = [
    path("patienten/<uuid:pk>/akte/", views.chart_view, name="chart"),
    path("patienten/<uuid:pk>/akte/kontakt/", views.encounter_create_view, name="encounter_create"),
    path(
        "patienten/<uuid:pk>/akte/kontakte/<uuid:lineage>/eintrag/",
        views.entry_create_view,
        name="entry_create",
    ),
    path(
        "patienten/<uuid:pk>/akte/<kind:kind>/<uuid:lineage>/",
        views.history_view,
        name="history",
    ),
    path(
        "patienten/<uuid:pk>/akte/<kind:kind>/<uuid:lineage>/korrigieren/",
        views.revise_view,
        name="revise",
    ),
    path(
        "patienten/<uuid:pk>/akte/<kind:kind>/<uuid:lineage>/irrtum/",
        views.error_view,
        name="error",
    ),
]
