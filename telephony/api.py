"""Internal API for the voice agent (#14 section 7), JSON over HTTP.

The agent has no database credentials. It gets exactly six things here:
the practice's fixed information, the appointment types patients may
request, the check of one preferred day, the creation of a request, the
creation of a callback and the record of a finished call (#45). No endpoint
reads existing requests, appointments, callbacks or patients, and the
answer to something new is only its reference or id: what the assistant
cannot read, a caller cannot talk it into revealing.

Every rule stays in `appointments/services.py` and `telephony/services.py`;
this module only turns JSON into the arguments of their functions.
"""

import hmac
import json
import uuid
from datetime import date, datetime
from functools import wraps

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from appointments import services
from appointments.forms import phone_validator
from appointments.models import AppointmentType, Channel, Insurance, PartOfDay
from practice import info
from practice.models import OpeningHours
from telephony import services as telephony_services

WEEKDAYS = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")

# Fields of a new request and their maximum length; anything else is refused,
# the note in particular (no free text on the phone, #14 section 5).
TEXT_FIELDS = {
    "patient_first_name": 100,
    "patient_last_name": 100,
    "contact_name": 200,
    "contact_relationship": 100,
    "privacy_notice_version": 40,
}
REQUEST_FIELDS = {
    *TEXT_FIELDS,
    "appointment_type",
    "is_existing_patient",
    "insurance_type",
    "patient_date_of_birth",
    "email",
    "phone",
    "time_windows",
}
REQUIRED_FIELDS = REQUEST_FIELDS - {"contact_name", "contact_relationship", "email"}
EMAIL_MAX_LENGTH = 254

# A callback: these fields and no others, no free text either (#45).
CALLBACK_FIELDS = {"name": 200, "phone": 40, "category": 20, "reference": 10}
CALLBACK_REQUIRED = {"name", "phone", "category"}
# The end of a call: when, how long, what happened; never a number or words.
CALL_FIELDS = {"started_at", "duration_seconds", "outcomes", "request_reference", "callback_id"}
CALL_REQUIRED = {"started_at", "duration_seconds", "outcomes"}


def internal(view):
    """Only with the key from `VOICE_API_KEY`; without a key set, the API is off.

    Off means 404, as if the path did not exist, never open. A missing or
    wrong key is 403. The key is compared in constant time.
    """

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        key = settings.VOICE_API_KEY
        if not key:
            raise Http404
        given = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if not hmac.compare_digest(given.encode(), key.encode()):
            return JsonResponse({"error": "forbidden"}, status=403)
        return view(request, *args, **kwargs)

    # A key, not a cookie, authenticates the caller: nothing for CSRF to protect.
    return csrf_exempt(never_cache(wrapped))


def _errors(error: ValidationError, status=400) -> JsonResponse:
    if hasattr(error, "error_dict"):
        return JsonResponse({"errors": error.message_dict}, status=status)
    return JsonResponse({"errors": {"__all__": error.messages}}, status=status)


def _body(request) -> dict:
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise ValidationError("Kein gültiges JSON.") from None
    if not isinstance(data, dict):
        raise ValidationError("Erwartet wird ein JSON-Objekt.")
    return data


def _date(value, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError({field: "Bitte ein Datum im Format JJJJ-MM-TT."}) from None


def _known_fields(data: dict, allowed: set, required: set) -> None:
    """Unknown fields are an error, not silently dropped: `note` must fail loudly."""
    errors = {}
    for field in sorted(data.keys() - allowed):
        errors[field] = "Dieses Feld gibt es am Telefon nicht."
    for field in sorted(required - data.keys()):
        errors[field] = "Fehlt."
    if errors:
        raise ValidationError(errors)


def _text(value, field: str, max_length: int) -> str:
    # NUL: PostgreSQL refuses it, and the answer would be 500, not 400.
    if not isinstance(value, str) or len(value.strip()) > max_length or "\x00" in value:
        raise ValidationError({field: f"Text mit höchstens {max_length} Zeichen."})
    return value.strip()


def _part_of_day(value, field: str) -> str:
    if value not in PartOfDay.values:
        raise ValidationError({field: "Bitte morning, afternoon oder any."})
    return value


# --- Information -------------------------------------------------------------


def _clock(value) -> str:
    return f"{value.hour} Uhr" if not value.minute else f"{value.hour}:{value.minute:02d} Uhr"


def _hours_text(blocks, closed_label: str) -> str:
    """One sentence per weekday, e.g. "Dienstag von 8 bis 13 Uhr und von 14 bis 17:30 Uhr"."""
    by_day: dict[int, list[str]] = {}
    for block in blocks:
        by_day.setdefault(block.weekday, []).append(
            f"von {_clock(block.opens).removesuffix(' Uhr')} bis {_clock(block.closes)}"
        )
    if not by_day:
        return ""
    days = [f"{WEEKDAYS[day]} {' und '.join(parts)}" for day, parts in sorted(by_day.items())]
    closed = [WEEKDAYS[day] for day in range(7) if day not in by_day]
    text = "; ".join(days) + "."
    if closed:
        text += f" {closed_label}: {', '.join(closed)}."
    return text


@internal
@require_GET
def practice_info(request):
    """Fixed answers by topic, only from `OpeningHours` and `practice/info.py`.

    An empty text means the practice has not entered anything; the
    assistant then says it does not know.
    """
    hours = OpeningHours.objects.order_by("weekday", "opens")
    return JsonResponse(
        {
            "topics": {
                "opening_hours": _hours_text(
                    hours.filter(kind=OpeningHours.Kind.OPENING), "Geschlossen"
                ),
                "consultation_hours": _hours_text(hours.consultation(), "Keine Sprechzeit"),
                "blood_draw": info.BLOOD_DRAW,
                "address": f"{info.NAME}, {info.STREET}, {info.CITY}. Telefon {info.PHONE}.",
                "access": info.ACCESS,
            }
        }
    )


@internal
@require_GET
def appointment_types(request):
    """The types patients may request online; nothing else on the phone either."""
    return JsonResponse(
        {"types": [{"id": t.pk, "name": t.public_name} for t in services.active_types()]}
    )


# --- Checking and creating ---------------------------------------------------


@internal
@require_POST
def check_time_window(request):
    """The check of the request form for one preferred day (#7).

    A day that does not fit is an answer (`ok: false` with the reason to
    read out), not an error; malformed input is 400.
    """
    try:
        data = _body(request)
        day = _date(data.get("date"), "date")
        part = _part_of_day(data.get("part_of_day"), "part_of_day")
    except ValidationError as error:
        return _errors(error)
    try:
        services.validate_time_window(day, part)
    except ValidationError as error:
        return JsonResponse({"ok": False, "reason": " ".join(error.messages)})
    return JsonResponse({"ok": True})


def _request_data(data: dict) -> dict:
    """JSON of the agent → `data` for `services.submit_request`; formats only."""
    _known_fields(data, REQUEST_FIELDS, REQUIRED_FIELDS)
    errors = {}
    result = {}
    for field, max_length in TEXT_FIELDS.items():
        try:
            result[field] = _text(data.get(field, ""), field, max_length)
        except ValidationError as error:
            errors.update(error.message_dict)
    for field in ("patient_first_name", "patient_last_name", "privacy_notice_version"):
        if field not in errors and not result[field]:
            errors[field] = "Fehlt."

    type_id = data["appointment_type"]
    try:
        # bool is an int in Python; `true` must not become id 1.
        if not isinstance(type_id, int) or isinstance(type_id, bool):
            raise TypeError
        result["appointment_type"] = services.active_types().get(pk=type_id)
    except (TypeError, OverflowError, AppointmentType.DoesNotExist):
        errors["appointment_type"] = "Diese Terminart kann nicht online angefragt werden."
    if isinstance(data["is_existing_patient"], bool):
        result["is_existing_patient"] = data["is_existing_patient"]
    else:
        errors["is_existing_patient"] = "Bitte true oder false."
    if data["insurance_type"] in Insurance.values:
        result["insurance_type"] = data["insurance_type"]
    else:
        errors["insurance_type"] = f"Bitte eins von {', '.join(Insurance.values)}."

    email = data.get("email", "")
    phone = data["phone"]
    try:
        # 254: the column; validate_email alone lets 320 characters through.
        if not isinstance(email, str) or len(email) > EMAIL_MAX_LENGTH:
            raise TypeError
        if email:
            validate_email(email)
        result["email"] = email
    except (ValidationError, TypeError):
        errors["email"] = "Bitte eine gültige E-Mail-Adresse oder keine."
    try:
        if not isinstance(phone, str):
            raise TypeError
        phone_validator(phone.strip())
        result["phone"] = phone.strip()
    except (ValidationError, TypeError):
        errors["phone"] = "Bitte eine Telefonnummer mit Ziffern."

    windows = data["time_windows"]
    result["time_windows"] = []
    if not isinstance(windows, list) or not all(isinstance(w, dict) for w in windows):
        errors["time_windows"] = "Bitte eine Liste von {date, part_of_day}."
    else:
        for position, window in enumerate(windows, start=1):
            try:
                result["time_windows"].append(
                    (
                        _date(window.get("date"), f"window_{position}"),
                        _part_of_day(window.get("part_of_day"), f"window_{position}"),
                    )
                )
            except ValidationError as error:
                errors.update(error.message_dict)
    try:
        result["patient_date_of_birth"] = _date(
            data["patient_date_of_birth"], "patient_date_of_birth"
        )
    except ValidationError as error:
        errors.update(error.message_dict)

    if errors:
        raise ValidationError(errors)
    return result


@internal
@require_POST
def create_request(request):
    """A new request with channel `phone_assistant`; the answer is only the reference.

    Without an e-mail address it starts `open`, with one `unverified` and
    the same confirmation mail as on the website (#14 section 5).
    """
    try:
        created = services.submit_request(
            _request_data(_body(request)), channel=Channel.PHONE_ASSISTANT
        )
    except ValidationError as error:
        return _errors(error)
    return JsonResponse({"reference": created.reference}, status=201)


@internal
@require_POST
def create_callback(request):
    """A new callback (#45); the answer is only its id, for the call record."""
    try:
        data = _body(request)
        _known_fields(data, CALLBACK_FIELDS.keys(), CALLBACK_REQUIRED)
        errors, fields = {}, {}
        for field, max_length in CALLBACK_FIELDS.items():
            try:
                fields[field] = _text(data.get(field, ""), field, max_length)
            except ValidationError as error:
                errors.update(error.message_dict)
        if errors:
            raise ValidationError(errors)
        created = telephony_services.create_callback(**fields)
    except ValidationError as error:
        return _errors(error)
    return JsonResponse({"id": str(created.pk)}, status=201)


def _call_data(data: dict) -> dict:
    """JSON of the agent → arguments of `record_call`; formats only."""
    _known_fields(data, CALL_FIELDS, CALL_REQUIRED)
    errors, result = {}, {}
    try:
        started_at = datetime.fromisoformat(data["started_at"])
        if started_at.tzinfo is None:
            raise ValueError
        result["started_at"] = started_at
    except (TypeError, ValueError):
        errors["started_at"] = "Bitte Datum und Uhrzeit nach ISO 8601 mit Zeitzone."
    duration = data["duration_seconds"]
    if isinstance(duration, int) and not isinstance(duration, bool):
        result["duration_seconds"] = duration
    else:
        errors["duration_seconds"] = "Bitte eine ganze Zahl."
    outcomes = data["outcomes"]
    if isinstance(outcomes, list) and all(isinstance(o, str) for o in outcomes):
        result["outcomes"] = outcomes
    else:
        errors["outcomes"] = "Bitte eine Liste von Ergebnissen."
    try:
        result["request_reference"] = _text(
            data.get("request_reference", ""), "request_reference", 10
        )
    except ValidationError as error:
        errors.update(error.message_dict)
    callback_id = data.get("callback_id")
    if callback_id is not None:
        try:
            result["callback_id"] = uuid.UUID(callback_id)
        except (TypeError, ValueError, AttributeError):
            errors["callback_id"] = "Bitte eine UUID."
    if errors:
        raise ValidationError(errors)
    return result


@internal
@require_POST
def record_call(request):
    """The end of a call (#45): time, duration, outcomes; no number, no content."""
    try:
        telephony_services.record_call(**_call_data(_body(request)))
    except ValidationError as error:
        return _errors(error)
    return JsonResponse({}, status=201)
