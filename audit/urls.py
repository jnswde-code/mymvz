from django.urls import path

from audit import views

app_name = "audit"

urlpatterns = [
    path("protokoll/", views.log_view, name="log"),
]
