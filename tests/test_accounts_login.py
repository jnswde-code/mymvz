"""Login in two steps; the second factor cannot be skipped (#25)."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.sessions.models import Session
from django.urls import reverse
from django.utils import timezone
from django_otp.plugins.otp_static.models import StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from accounts import views
from accounts.second_factor import new_recovery_codes
from accounts.testing import (
    PASSWORD,
    add_totp_device,
    current_code,
    login_with_second_factor,
    make_user,
)

pytestmark = pytest.mark.django_db

LOGIN = reverse("accounts:login")
VERIFY = reverse("accounts:verify")
SETUP = reverse("accounts:setup")
ACCOUNT = reverse("accounts:account")
AUDIT_LOG = reverse("audit:log")


def password_step(client, username="erika.beispiel", password=PASSWORD, **extra):
    return client.post(LOGIN, {"username": username, "password": password, **extra})


def is_logged_in(client):
    return client.get(ACCOUNT).status_code == 200


def test_wrong_password_is_rejected(client):
    make_user()
    response = password_step(client, password="falsch-falsch-falsch")
    assert response.status_code == 200
    assert views.INVALID_LOGIN in response.text
    assert not is_logged_in(client)


def test_unknown_user_gets_the_same_message(client):
    response = password_step(client, username="niemand")
    assert views.INVALID_LOGIN in response.text


def test_inactive_account_cannot_log_in(client):
    add_totp_device(make_user(is_active=False))
    response = password_step(client)
    assert views.INVALID_LOGIN in response.text


@pytest.mark.parametrize("url", [ACCOUNT, AUDIT_LOG])
def test_password_alone_opens_no_protected_page(client, url):
    add_totp_device(make_user(roles=["Verwaltung"]))
    assert password_step(client).url == VERIFY
    response = client.get(url)
    assert response.status_code == 302
    assert response.url.startswith(LOGIN)


def test_code_step_needs_the_password_step(client):
    assert client.get(VERIFY).url == LOGIN
    assert client.post(VERIFY, {"code": "123456"}).url == LOGIN
    assert client.get(SETUP).url == LOGIN


def test_correct_code_logs_in(client):
    device = add_totp_device(make_user())
    password_step(client)
    response = client.post(VERIFY, {"code": current_code(device)})
    assert response.url == ACCOUNT
    assert is_logged_in(client)


def test_wrong_code_does_not_log_in(client):
    add_totp_device(make_user())
    password_step(client)
    response = client.post(VERIFY, {"code": "000000"})
    assert views.INVALID_CODE in response.text
    assert not is_logged_in(client)


def test_code_cannot_be_replayed(client):
    device = add_totp_device(make_user())
    code = current_code(device)
    password_step(client)
    client.post(VERIFY, {"code": code})
    client.post(reverse("accounts:logout"))
    password_step(client)
    assert views.INVALID_CODE in client.post(VERIFY, {"code": code}).text


def test_code_step_expires(client):
    device = add_totp_device(make_user())
    password_step(client)
    session = client.session
    session[views.PENDING_SINCE] -= views.PENDING_SECONDS + 1
    session.save()
    assert client.post(VERIFY, {"code": current_code(device)}).url == LOGIN
    assert not is_logged_in(client)


def test_deactivated_between_steps(client):
    user = make_user()
    device = add_totp_device(user)
    password_step(client)
    user.is_active = False
    user.save()
    assert client.post(VERIFY, {"code": current_code(device)}).url == LOGIN


def test_first_login_sets_up_app_and_shows_recovery_codes(client):
    user = make_user()
    assert password_step(client).url == SETUP
    page = client.get(SETUP)
    assert "<svg" in page.text
    device = TOTPDevice.objects.get(user=user, confirmed=False)
    # The same secret on reload, so a scanned code stays valid.
    client.get(SETUP)
    assert TOTPDevice.objects.filter(user=user).count() == 1

    response = client.post(SETUP, {"code": current_code(device)})
    codes = response.context["codes"]
    assert len(codes) == 10
    assert all(code in response.text for code in codes)
    assert response["Cache-Control"].startswith("max-age=0")
    device.refresh_from_db()
    assert device.confirmed
    assert is_logged_in(client)


def test_setup_with_wrong_code_confirms_nothing(client):
    user = make_user()
    password_step(client)
    client.get(SETUP)
    response = client.post(SETUP, {"code": "000000"})
    assert views.INVALID_CODE in response.text
    assert not TOTPDevice.objects.filter(user=user, confirmed=True).exists()
    assert not is_logged_in(client)


def test_password_alone_cannot_register_another_app(client):
    user = make_user()
    add_totp_device(user)
    password_step(client)
    assert client.get(SETUP).url == VERIFY
    assert client.post(SETUP, {"code": "123456"}).url == VERIFY
    assert TOTPDevice.objects.filter(user=user).count() == 1


def test_recovery_code_works_once(client):
    user = make_user()
    add_totp_device(user)
    code = new_recovery_codes(user)[0]
    password_step(client)
    assert client.post(VERIFY, {"code": code.upper()}).url == ACCOUNT
    assert StaticToken.objects.filter(device__user=user).count() == 9

    client.post(reverse("accounts:logout"))
    password_step(client)
    assert views.INVALID_CODE in client.post(VERIFY, {"code": code}).text


def test_forced_login_without_second_factor_is_ended(client):
    user = make_user()
    client.force_login(user)
    assert client.get(ACCOUNT).status_code == 302
    assert "_auth_user_id" not in client.session


def test_removed_device_ends_open_session(client):
    user = make_user()
    login_with_second_factor(client, user)
    assert is_logged_in(client)
    TOTPDevice.objects.filter(user=user).delete()
    assert not is_logged_in(client)


def test_deactivated_account_loses_open_session(client):
    user = make_user()
    login_with_second_factor(client, user)
    user.is_active = False
    user.save()
    assert not is_logged_in(client)


def test_session_key_changes_at_each_step(client):
    device = add_totp_device(make_user())
    client.get(LOGIN)
    password_step(client)
    after_password = client.session.session_key
    client.post(VERIFY, {"code": current_code(device)})
    assert client.session.session_key != after_password


def test_next_is_followed_only_on_this_site(client):
    device = add_totp_device(make_user())
    password_step(client, next=AUDIT_LOG)
    assert client.post(VERIFY, {"code": current_code(device)}).url == AUDIT_LOG

    client.post(reverse("accounts:logout"))
    device.last_t = -1
    device.save()
    password_step(client, next="https://evil.example/")
    assert client.post(VERIFY, {"code": current_code(device)}).url == ACCOUNT


def test_next_survives_a_wrong_password(client):
    make_user()
    response = client.post(
        f"{LOGIN}?next={AUDIT_LOG}",
        {"username": "erika.beispiel", "password": "falsch-falsch-falsch", "next": AUDIT_LOG},
    )
    assert response.context["next"] == AUDIT_LOG


@pytest.mark.parametrize("spacing", ["{} {}", "{}-{}", " {}{} "])
def test_codes_may_contain_spaces_and_dashes(client, spacing):
    user = make_user()
    device = add_totp_device(user)
    code = current_code(device)
    password_step(client)
    assert client.post(VERIFY, {"code": spacing.format(code[:3], code[3:])}).url == ACCOUNT


def test_recovery_code_with_dash(client):
    user = make_user()
    add_totp_device(user)
    code = new_recovery_codes(user)[0]
    password_step(client)
    assert client.post(VERIFY, {"code": f"{code[:4]}-{code[4:]}"}).url == ACCOUNT


def test_setup_survives_a_vanished_device(client):
    user = make_user()
    password_step(client)
    client.get(SETUP)
    old = TOTPDevice.objects.get(user=user)
    code = current_code(old)
    # E.g. a second tab confirmed a different device, or a reset ran.
    with patch("accounts.second_factor.pending_totp_device", return_value=old):
        TOTPDevice.objects.filter(pk=old.pk).delete()
        response = client.post(SETUP, {"code": code})
    assert response.status_code == 200
    assert views.INVALID_CODE in response.text
    assert not is_logged_in(client)


def test_logout_needs_post(client):
    login_with_second_factor(client, make_user())
    assert client.get(reverse("accounts:logout")).status_code == 405
    assert client.post(reverse("accounts:logout")).url == LOGIN
    assert not is_logged_in(client)


def test_session_settings(settings):
    assert settings.SESSION_COOKIE_AGE == 30 * 60
    assert settings.SESSION_SAVE_EVERY_REQUEST
    assert settings.SESSION_EXPIRE_AT_BROWSER_CLOSE


def test_session_ends_after_inactivity(client):
    login_with_second_factor(client, make_user())
    assert is_logged_in(client)
    Session.objects.update(expire_date=timezone.now() - timedelta(seconds=1))
    assert not is_logged_in(client)


def test_activity_extends_the_session(client):
    login_with_second_factor(client, make_user())
    Session.objects.update(expire_date=timezone.now() + timedelta(minutes=1))
    assert is_logged_in(client)
    remaining = Session.objects.get().expire_date - timezone.now()
    assert remaining > timedelta(minutes=29)
