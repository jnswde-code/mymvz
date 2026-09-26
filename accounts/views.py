"""Login in two steps: password, then a code from the app (#25).

Django's `login()` runs only after the second step. Between the steps the
session holds nothing but the pending user's id, so `request.user` stays
anonymous and every `login_required` view stays closed. The middleware in
`accounts/middleware.py` backs this up for sessions logged in any other way.
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, logout
from django.contrib.auth import login as django_login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, resolve_url
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST
from django_otp import login as otp_login

from accounts import second_factor, throttle
from accounts.forms import CodeForm, LoginForm

PENDING_USER = "accounts_pending_user"
PENDING_SINCE = "accounts_pending_since"
PENDING_NEXT = "accounts_pending_next"
# Time between password and code; long enough to set up the app.
PENDING_SECONDS = 10 * 60

INVALID_LOGIN = "Benutzername oder Passwort ist falsch."
INVALID_CODE = "Der Code stimmt nicht."
LOCKED = "Zu viele Fehlversuche. Bitte in 15 Minuten erneut versuchen."


def _safe_next(request, url):
    if url and url_has_allowed_host_and_scheme(
        url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return url
    return resolve_url(settings.LOGIN_REDIRECT_URL)


def _clear_pending(request):
    for key in (PENDING_USER, PENDING_SINCE, PENDING_NEXT):
        request.session.pop(key, None)


def _pending_user(request):
    """The user who passed the password step, if that is recent enough."""
    user_id = request.session.get(PENDING_USER)
    since = request.session.get(PENDING_SINCE)
    if not user_id or since is None or timezone.now().timestamp() - since > PENDING_SECONDS:
        _clear_pending(request)
        return None
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        _clear_pending(request)
    return user


def _complete_login(request, user, device):
    next_url = request.session.get(PENDING_NEXT)
    _clear_pending(request)
    throttle.reset_account(user.get_username())
    django_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    otp_login(request, device)
    return next_url


@sensitive_post_parameters("password")
@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request, request.GET.get("next")))
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        keys = throttle.request_keys(request, username)
        if not throttle.begin_attempt(keys):
            form.add_error(None, LOCKED)
        else:
            user = authenticate(request, username=username, password=form.cleaned_data["password"])
            if user is None:
                throttle.attempt_failed(keys)
                form.add_error(None, INVALID_LOGIN)
            else:
                throttle.attempt_succeeded(keys)
                request.session.cycle_key()
                request.session[PENDING_USER] = str(user.pk)
                request.session[PENDING_SINCE] = timezone.now().timestamp()
                request.session[PENDING_NEXT] = request.POST.get("next", "")
                if second_factor.confirmed_totp_device(user) is None:
                    # A fresh secret per login: whoever saw an earlier one
                    # without confirming it must not share the final one.
                    second_factor.discard_pending_devices(user)
                    return redirect("accounts:setup")
                return redirect("accounts:verify")
    next_url = request.POST.get("next") or request.GET.get("next", "")
    return render(request, "accounts/login.html", {"form": form, "next": next_url})


@never_cache
def verify_view(request):
    user = _pending_user(request)
    if user is None:
        return redirect("accounts:login")
    if second_factor.confirmed_totp_device(user) is None:
        return redirect("accounts:setup")
    form = CodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        keys = throttle.request_keys(request, user.get_username())
        if not throttle.begin_attempt(keys):
            form.add_error(None, LOCKED)
        else:
            device = second_factor.verify(user, form.cleaned_data["code"])
            if device is None:
                throttle.attempt_failed(keys)
                form.add_error("code", INVALID_CODE)
            else:
                throttle.attempt_succeeded(keys)
                next_url = _complete_login(request, user, device)
                return redirect(_safe_next(request, next_url))
    return render(request, "accounts/verify.html", {"form": form})


@never_cache
def setup_view(request):
    user = _pending_user(request)
    if user is None:
        return redirect("accounts:login")
    # Only for accounts without a device. Otherwise the password alone would
    # be enough to register a second app.
    if second_factor.confirmed_totp_device(user) is not None:
        return redirect("accounts:verify")
    device = second_factor.pending_totp_device(user)
    form = CodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        keys = throttle.request_keys(request, user.get_username())
        if not throttle.begin_attempt(keys):
            form.add_error(None, LOCKED)
        else:
            codes = second_factor.confirm_totp_device(device, form.cleaned_data["code"])
            if codes is None:
                throttle.attempt_failed(keys)
                form.add_error("code", INVALID_CODE)
                # The device may have gone meanwhile (second tab, reset).
                device = second_factor.pending_totp_device(user)
            else:
                throttle.attempt_succeeded(keys)
                device.refresh_from_db()
                next_url = _complete_login(request, user, device)
                # Shown exactly once, in this response; never stored in the session.
                return render(
                    request,
                    "accounts/recovery_codes.html",
                    {"codes": codes, "next": _safe_next(request, next_url)},
                )
    return render(
        request,
        "accounts/setup.html",
        {
            "form": form,
            "qr_code": second_factor.qr_code_svg(device),
            "manual_key": second_factor.manual_key(device),
        },
    )


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "Sie sind abgemeldet.")
    return redirect("accounts:login")


@login_required
@never_cache
def account_view(request):
    return render(
        request,
        "accounts/account.html",
        {
            "roles": request.user.groups.order_by("name").values_list("name", flat=True),
            "recovery_codes_left": second_factor.remaining_recovery_codes(request.user),
        },
    )
