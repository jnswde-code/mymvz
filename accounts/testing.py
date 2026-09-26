"""Helpers for tests in every app that needs a logged-in account.

Only invented people (#3). `login_with_second_factor` is the test-client
equivalent of both login steps; `client.force_login` alone is not enough,
because `RequireSecondFactorMiddleware` ends unverified sessions.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice

PASSWORD = "Probe-Passwort-2026"


def make_user(username="erika.beispiel", *, roles=(), password=PASSWORD, **fields):
    user = get_user_model().objects.create_user(username=username, password=password, **fields)
    user.groups.set(Group.objects.filter(name__in=roles))
    return user


def add_totp_device(user):
    return TOTPDevice.objects.create(user=user, name="Test", confirmed=True)


def current_code(device) -> str:
    totp = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift)
    return f"{totp.token():0{device.digits}d}"


def login_with_second_factor(client, user):
    device = TOTPDevice.objects.filter(user=user, confirmed=True).first() or add_totp_device(user)
    client.force_login(user)
    session = client.session
    session[DEVICE_ID_SESSION_KEY] = device.persistent_id
    session.save()
    return device
