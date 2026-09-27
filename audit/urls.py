from django.urls import path

from audit import views

app_name = "audit"

urlpatterns = [
    path("protokoll/", views.log_view, name="log"),
    path("protokoll/notfallzugriffe/", views.emergency_list_view, name="emergency_list"),
]
