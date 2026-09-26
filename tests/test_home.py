import pytest
from django.db import OperationalError, connection


@pytest.mark.django_db
def test_home_shows_database_running(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Anwendung und Datenbank laufen." in response.text


def test_home_reports_unreachable_database(client, monkeypatch):
    def fail():
        raise OperationalError("connection refused")

    monkeypatch.setattr(connection, "ensure_connection", fail)
    response = client.get("/")
    assert response.status_code == 503
    assert "Die Datenbank ist nicht erreichbar." in response.text


def test_unknown_host_is_rejected(client, settings):
    settings.ALLOWED_HOSTS = ["mymvz.jnsw.de"]
    assert client.get("/", HTTP_HOST="evil.example").status_code == 400
