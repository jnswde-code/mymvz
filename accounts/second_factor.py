"""TOTP devices and recovery codes, built on django-otp (#25)."""

import re
from base64 import b32encode

import qrcode
import qrcode.image.svg
from django.contrib.auth import get_user_model
from django.db import transaction
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

RECOVERY_CODE_COUNT = 10
_TOTP_CODE = re.compile(r"\d{6}")


def confirmed_totp_device(user):
    return TOTPDevice.objects.filter(user=user, confirmed=True).first()


def pending_totp_device(user):
    """The device being set up; the same one on every reload of the page."""
    with transaction.atomic():
        # Locking the user keeps two parallel loads from creating two secrets.
        get_user_model().objects.select_for_update().get(pk=user.pk)
        device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
        if device is None:
            device = TOTPDevice.objects.create(user=user, name="Authenticator-App", confirmed=False)
    return device


def discard_pending_devices(user) -> None:
    TOTPDevice.objects.filter(user=user, confirmed=False).delete()


def manual_key(device) -> str:
    """The secret in groups of four, for typing it into an app by hand."""
    key = b32encode(device.bin_key).decode()
    return " ".join(key[i : i + 4] for i in range(0, len(key), 4))


def qr_code_svg(device) -> str:
    image = qrcode.make(device.config_url, image_factory=qrcode.image.svg.SvgPathImage)
    return image.to_string(encoding="unicode")


def _normalize(code: str) -> str:
    return re.sub(r"[\s-]", "", code).lower()


def verify(user, code: str):
    """The confirmed device that accepts `code`, or None.

    Six digits go to the app, anything else to the recovery codes. Trying both
    would count every miss twice in django-otp's per-device delay.
    """
    code = _normalize(code)
    if _TOTP_CODE.fullmatch(code):
        model = TOTPDevice
    else:
        model = StaticDevice
    with transaction.atomic():
        device = model.objects.select_for_update().filter(user=user, confirmed=True).first()
        if device is not None and device.verify_token(code):
            return device
    return None


def confirm_totp_device(device, code: str) -> list[str] | None:
    """Confirm the device being set up; returns fresh recovery codes."""
    with transaction.atomic():
        device = TOTPDevice.objects.select_for_update().filter(pk=device.pk).first()
        if device is None or not device.verify_token(_normalize(code)):
            return None
        device.confirmed = True
        device.save()
        TOTPDevice.objects.filter(user=device.user, confirmed=False).delete()
        return new_recovery_codes(device.user)


def new_recovery_codes(user) -> list[str]:
    """Replace all recovery codes of `user`; each code works once."""
    StaticDevice.objects.filter(user=user).delete()
    device = StaticDevice.objects.create(user=user, name="Wiederherstellungscodes")
    codes = [StaticToken.random_token() for _ in range(RECOVERY_CODE_COUNT)]
    StaticToken.objects.bulk_create(StaticToken(device=device, token=c) for c in codes)
    return codes


def remaining_recovery_codes(user) -> int:
    return StaticToken.objects.filter(device__user=user, device__confirmed=True).count()


def remove_all_devices(user) -> None:
    """Force a new setup at the next login; open sessions end with it."""
    TOTPDevice.objects.filter(user=user).delete()
    StaticDevice.objects.filter(user=user).delete()
