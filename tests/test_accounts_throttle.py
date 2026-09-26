"""Lock after failed attempts, per account name and per address (#25)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts import throttle, views
from accounts.models import LoginThrottle
from accounts.testing import PASSWORD, add_totp_device, current_code, make_user

pytestmark = pytest.mark.django_db

LOGIN = reverse("accounts:login")
VERIFY = reverse("accounts:verify")


def attempt(client, username="erika.beispiel", password="falsch-falsch-falsch", address=None):
    extra = {"REMOTE_ADDR": address} if address else {}
    return client.post(LOGIN, {"username": username, "password": password}, **extra)


def test_account_is_locked_after_limit(client):
    make_user()
    for _ in range(throttle.ACCOUNT_LIMIT):
        assert views.INVALID_LOGIN in attempt(client).text
    # Even the right password is not checked while locked.
    response = attempt(client, password=PASSWORD)
    assert views.LOCKED in response.text
    assert views.PENDING_USER not in client.session


def test_below_limit_is_not_locked(client):
    make_user()
    for _ in range(throttle.ACCOUNT_LIMIT - 1):
        attempt(client)
    assert attempt(client, password=PASSWORD).status_code == 302


def test_lock_is_per_account_name_in_any_case(client):
    make_user()
    make_user("max.muster")
    for _ in range(throttle.ACCOUNT_LIMIT):
        attempt(client, username="Erika.Beispiel ")
    assert views.LOCKED in attempt(client, password=PASSWORD).text
    assert attempt(client, username="max.muster", password=PASSWORD).status_code == 302


def test_lock_ends(client):
    make_user()
    for _ in range(throttle.ACCOUNT_LIMIT):
        attempt(client)
    LoginThrottle.objects.update(locked_until=timezone.now() - timedelta(seconds=1))
    assert attempt(client, password=PASSWORD).status_code == 302


def test_old_failures_expire(client):
    make_user()
    for _ in range(throttle.ACCOUNT_LIMIT - 1):
        attempt(client)
    LoginThrottle.objects.update(window_start=timezone.now() - throttle.WINDOW * 2)
    attempt(client)
    assert attempt(client, password=PASSWORD).status_code == 302


def test_unknown_names_lock_the_same_way(client):
    for _ in range(throttle.ACCOUNT_LIMIT):
        attempt(client, username="niemand")
    assert views.LOCKED in attempt(client, username="niemand").text


def test_address_is_locked_across_names(client):
    make_user()
    for i in range(throttle.ADDRESS_LIMIT):
        attempt(client, username=f"probe{i}", address="203.0.113.7")
    assert views.LOCKED in attempt(client, password=PASSWORD, address="203.0.113.7").text
    assert attempt(client, password=PASSWORD, address="198.51.100.4").status_code == 302


def test_wrong_codes_lock_the_account(client):
    device = add_totp_device(make_user())
    client.post(LOGIN, {"username": "erika.beispiel", "password": PASSWORD})
    for _ in range(throttle.ACCOUNT_LIMIT):
        client.post(VERIFY, {"code": "000000"})
    assert views.LOCKED in client.post(VERIFY, {"code": current_code(device)}).text


def test_complete_login_resets_the_account_counter(client):
    device = add_totp_device(make_user())
    for _ in range(throttle.ACCOUNT_LIMIT - 1):
        attempt(client)
    attempt(client, password=PASSWORD)
    client.post(VERIFY, {"code": current_code(device)})
    assert not LoginThrottle.objects.filter(key=throttle.account_key("erika.beispiel")).exists()


def test_neither_address_nor_name_is_stored(client):
    attempt(client, username="erika.beispiel", address="203.0.113.7")
    for entry in LoginThrottle.objects.all():
        assert "203.0.113" not in entry.key
        assert "erika" not in entry.key
        assert len(entry.key) == 64


def test_attempts_in_flight_count_against_the_limit():
    """Parallel requests cannot all pass the check before any is counted."""
    keys = [(throttle.account_key("erika.beispiel"), throttle.ACCOUNT_LIMIT)]
    for _ in range(throttle.ACCOUNT_LIMIT):
        assert throttle.begin_attempt(keys)
    assert not throttle.begin_attempt(keys)


def test_successful_attempt_is_forgiven():
    keys = [(throttle.account_key("erika.beispiel"), throttle.ACCOUNT_LIMIT)]
    for _ in range(throttle.ACCOUNT_LIMIT * 2):
        assert throttle.begin_attempt(keys)
        throttle.attempt_succeeded(keys)


def test_purge_removes_rows_after_their_window():
    keys = [(throttle.address_key("203.0.113.7"), throttle.ADDRESS_LIMIT)]
    throttle.begin_attempt(keys)
    throttle.attempt_failed(keys)
    LoginThrottle.objects.update(window_start=timezone.now() - throttle.WINDOW * 2)
    throttle.purge_expired()
    assert not LoginThrottle.objects.exists()
