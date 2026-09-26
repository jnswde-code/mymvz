from django.urls import include, path

from config import views

urlpatterns = [
    path("", views.home, name="home"),
    path("", include("accounts.urls")),
    path("", include("audit.urls")),
]
