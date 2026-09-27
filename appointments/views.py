"""Pages for patients: the request form and the links from e-mails (#7).

The team's views belong to #8. No login here; a link is as good as its
token, and the pages only show date, time and reference.
"""

from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from appointments import captcha, services, spam
from appointments.forms import CancelForm, RequestForm
from appointments.models import Channel, TokenPurpose
from appointments.tokens import Problem

CAPTCHA_FAILED = (
    "Die automatische Prüfung gegen Spam ist nicht abgeschlossen oder abgelaufen. "
    "Bitte warten Sie einen Moment und senden Sie die Anfrage erneut."
)


@never_cache
@require_http_methods(["GET", "POST"])
def request_form(request):
    if request.method == "POST":
        if not spam.allow_submission(request):
            return render(request, "appointments/too_many.html", status=429)
        if request.POST.get(spam.HONEYPOT_FIELD):
            # Look like success, so the bot learns nothing.
            return redirect("appointments:sent")
        form = RequestForm(request.POST)
        if form.is_valid():
            if not captcha.verify(form.cleaned_data["altcha"]):
                form.add_error(None, CAPTCHA_FAILED)
            else:
                try:
                    services.submit_request(form.service_data(), channel=Channel.WEB)
                except ValidationError as error:
                    form.add_service_errors(error)
                else:
                    return redirect("appointments:sent")
    else:
        form = RequestForm()
    return render(
        request,
        "appointments/request_form.html",
        {
            "form": form,
            "challenge": captcha.create_challenge(),
            "has_types": services.active_types().exists(),
        },
    )


def request_sent(request):
    return render(request, "appointments/request_sent.html")


def privacy_notice(request):
    """Privacy notice of the appointment pages (#11).

    Deadlines come from the settings the code uses. The date shown is the
    version stored with every request, an ISO date; changing a deadline or
    the text needs a new one.
    """
    return render(
        request,
        "appointments/privacy_notice.html",
        {
            "version": date.fromisoformat(settings.APPOINTMENTS_PRIVACY_NOTICE_VERSION),
            "retention_days": settings.APPOINTMENTS_RETENTION_DAYS,
            "verify_hours": int(settings.APPOINTMENTS_VERIFY_EMAIL_WITHIN.total_seconds() // 3600),
            "proposal_working_days": settings.APPOINTMENTS_PROPOSAL_WORKING_DAYS,
            "csrf_cookie_days": settings.CSRF_COOKIE_AGE // (24 * 60 * 60),
        },
    )


_PAGES = {
    TokenPurpose.VERIFY_EMAIL: "appointments/link_verify.html",
    TokenPurpose.WITHDRAW: "appointments/link_withdraw.html",
    TokenPurpose.RESPOND_TO_PROPOSAL: "appointments/link_respond.html",
    TokenPurpose.CANCEL: "appointments/link_cancel.html",
}


def _invalid(request, problem, token=None):
    purpose = token.purpose if token is not None else None
    status = 404 if problem == Problem.UNKNOWN else 410
    return render(
        request,
        "appointments/link_invalid.html",
        {"problem": problem, "purpose": purpose},
        status=status,
    )


def _act(request, token, raw):
    """Carry out the link's action; returns the name of the result page."""
    match token.purpose:
        case TokenPurpose.VERIFY_EMAIL:
            services.verify_email(raw)
            return "verified"
        case TokenPurpose.WITHDRAW:
            services.withdraw_request(raw)
            return "withdrawn"
        case TokenPurpose.RESPOND_TO_PROPOSAL:
            if request.POST.get("decision") == "accept":
                services.accept_proposal(raw)
                return "accepted"
            if request.POST.get("decision") == "decline":
                services.decline_proposal(raw)
                return "declined"
            return None
        case TokenPurpose.CANCEL:
            form = CancelForm(request.POST)
            if not form.is_valid():
                return None
            services.cancel_by_patient(raw, form.cleaned_data["reason"])
            return "cancelled"
    return None


@never_cache
@require_http_methods(["GET", "POST"])
def link(request, token):
    """GET shows what the link does, POST does it.

    Mail filters open links to scan them; a GET must therefore never change
    anything, or a scanner could cancel an appointment.
    """
    found = services.check_link(token)
    if not found.ok:
        return _invalid(request, found.problem, found.token)
    context = {
        "reference": found.token.request.reference,
        "appointment": found.token.appointment,
        "cancel_form": CancelForm(),
    }
    if request.method == "POST":
        try:
            result = _act(request, found.token, token)
        except services.LinkInvalid as error:
            return _invalid(request, error.problem, error.token)
        if result is not None:
            return render(request, "appointments/link_done.html", {**context, "result": result})
    return render(request, _PAGES[found.token.purpose], context)
