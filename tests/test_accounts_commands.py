"""Accounts are created and deactivated on the command line (#25)."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command
from django.db.models import ProtectedError
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

from accounts import roles
from accounts.management.commands import create_account
from accounts.second_factor import new_recovery_codes
from accounts.testing import PASSWORD, add_totp_device, make_user

pytestmark = pytest.mark.django_db


def typed(monkeypatch, *answers):
    answers = iter(answers)
    monkeypatch.setattr(create_account, "getpass", lambda prompt: next(answers))


def test_create_account_with_roles(monkeypatch):
    typed(monkeypatch, PASSWORD, PASSWORD)
    call_command("create_account", "max.muster", "--role", "mfa", "--role", "administration")
    user = get_user_model().objects.get(username="max.muster")
    assert user.check_password(PASSWORD)
    assert set(user.groups.values_list("name", flat=True)) == {roles.MFA, roles.ADMINISTRATION}
    assert not user.is_staff and not user.is_superuser


def test_create_account_rejects_weak_password(monkeypatch):
    typed(monkeypatch, "kurz", "kurz")
    with pytest.raises(CommandError):
        call_command("create_account", "max.muster", "--role", "mfa")
    assert not get_user_model().objects.exists()


def test_create_account_rejects_mismatch(monkeypatch):
    typed(monkeypatch, PASSWORD, PASSWORD + "x")
    with pytest.raises(CommandError):
        call_command("create_account", "max.muster", "--role", "mfa")


def test_create_account_rejects_duplicate(monkeypatch):
    make_user("max.muster")
    typed(monkeypatch, PASSWORD, PASSWORD)
    with pytest.raises(CommandError):
        call_command("create_account", "max.muster", "--role", "mfa")


def test_create_account_fails_without_role_groups(monkeypatch):
    Group.objects.filter(name=roles.ADMINISTRATION).delete()
    typed(monkeypatch, PASSWORD, PASSWORD)
    with pytest.raises(CommandError):
        call_command("create_account", "max.muster", "--role", "administration")
    assert not get_user_model().objects.exists()


def test_create_account_needs_a_known_role():
    with pytest.raises(CommandError):
        call_command("create_account", "max.muster", "--role", "chef")


def test_deactivate_account():
    make_user("max.muster")
    call_command("deactivate_account", "max.muster")
    assert not get_user_model().objects.get(username="max.muster").is_active
    with pytest.raises(CommandError):
        call_command("deactivate_account", "niemand")


def test_accounts_are_never_deleted():
    user = make_user()
    with pytest.raises(ProtectedError):
        user.delete()
    assert get_user_model().objects.filter(pk=user.pk).exists()


def test_reset_second_factor():
    user = make_user()
    add_totp_device(user)
    new_recovery_codes(user)
    call_command("reset_second_factor", user.username)
    assert not TOTPDevice.objects.filter(user=user).exists()
    assert not StaticDevice.objects.filter(user=user).exists()
