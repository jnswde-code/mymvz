from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("anmelden/", views.login_view, name="login"),
    path("anmelden/code/", views.verify_view, name="verify"),
    path("anmelden/einrichten/", views.setup_view, name="setup"),
    path("abmelden/", views.logout_view, name="logout"),
    path("konto/", views.account_view, name="account"),
]
