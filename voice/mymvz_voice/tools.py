"""Tools of the LLM that read practice information and create requests (#14 section 7).

The list is final: fixed information, the check of a preferred day, a new
request and a new callback (#45). There is no tool that reads existing
requests, appointments, callbacks or people. Everything goes through the
internal API of the web app; the rules live there (`appointments/services.py`,
`telephony/services.py`), not here.

`hand_off` and `end_call` stay on the agent, next to the safety switch.
"""

from __future__ import annotations

import logging
from datetime import date
from enum import StrEnum

from livekit.agents import RunContext, StopResponse, ToolError, function_tool
from livekit.agents.llm import Tool
from pydantic import BaseModel

from . import texts
from .api_client import ApiClient, ApiRejected, ApiUnavailable
from .call_report import CallReport, Outcome

WEEKDAYS = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
MONTHS = (
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)

UNKNOWN = "Dazu liegt mir nichts vor."
# Several people in one call are fine (e.g. two children); more looks like abuse.
MAX_REQUESTS_PER_CALL = 3
MAX_CALLBACKS_PER_CALL = 3

logger = logging.getLogger("mymvz_voice.tools")


class Topic(StrEnum):
    OPENING_HOURS = "opening_hours"
    CONSULTATION_HOURS = "consultation_hours"
    BLOOD_DRAW = "blood_draw"
    ADDRESS = "address"
    ACCESS = "access"
    APPOINTMENT_TYPES = "appointment_types"


class PartOfDay(StrEnum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    ANY = "any"


class Insurance(StrEnum):
    STATUTORY = "statutory"
    PRIVATE = "private"
    SELF_PAY = "self_pay"


class CallbackCategory(StrEnum):
    """The fixed list of `telephony.models.CallbackCategory`."""

    PRESCRIPTION = "prescription"
    REFERRAL = "referral"
    SICK_NOTE = "sick_note"
    FINDINGS = "findings"
    DOCTOR_CALLBACK = "doctor_callback"
    CANCEL_OR_MOVE = "cancel_or_move"
    OTHER = "other"


class TimeWindow(BaseModel):
    date: str
    part_of_day: PartOfDay


def today_line(today: date) -> str:
    """For the instructions, so that "next Tuesday" is computed from the right day."""
    return (
        f"Heute ist {WEEKDAYS[today.weekday()]}, der {today.day}. "
        f"{MONTHS[today.month - 1]} {today.year} ({today.isoformat()})."
    )


def spell(reference: str) -> str:
    """ "A-7K3F9" → "A 7 K 3 F 9", so the TTS reads it character by character."""
    return " ".join(reference.replace("-", ""))


def _unavailable(
    context: RunContext, error: ApiUnavailable, tool: str, report: CallReport
) -> StopResponse:
    """Never silent when the API fails: a fixed sentence instead of a guess."""
    # Only the reason (status or exception type), never what was sent.
    logger.warning("interne API nicht verfügbar bei %s: %s", tool, error)
    report.note(Outcome.FAILED)
    context.session.say(texts.API_UNAVAILABLE)
    return StopResponse()


def _rejected(error: ApiRejected, prefix: str) -> ToolError:
    messages = "; ".join(
        f"{field}: {' '.join(m if isinstance(m, str) else str(m) for m in found)}"
        for field, found in error.errors.items()
    )
    return ToolError(f"{prefix} Bitte nachfragen und korrigieren. {messages}")


def phone_tools(api: ApiClient, report: CallReport | None = None) -> list[Tool]:
    """The tools for one call; they count the requests and callbacks of this call."""
    report = report or CallReport()
    call = {"created": 0, "create_failed": False, "callbacks": 0, "callback_failed": False}

    @function_tool
    async def get_practice_info(context: RunContext, topic: Topic) -> str:
        """Liefert feste Auskünfte der Praxis. Nur was hier steht, darfst du sagen.

        topic: opening_hours (Öffnungszeiten), consultation_hours
        (Sprechzeiten), blood_draw (Blutabnahme), address (Anschrift und
        Telefon), access (Anfahrt und barrierefreier Zugang),
        appointment_types (Terminarten, die man anfragen kann, mit ihrer id).
        """
        try:
            if topic is Topic.APPOINTMENT_TYPES:
                types = await api.appointment_types()
                if not types:
                    return "Zurzeit kann keine Terminart angefragt werden."
                answer = "Terminarten: " + "; ".join(f"id {t['id']}: {t['name']}" for t in types)
            else:
                answer = (await api.practice_info()).get(topic.value) or UNKNOWN
        except ApiUnavailable as error:
            raise _unavailable(context, error, "get_practice_info", report) from None
        report.note(Outcome.INFO)
        return answer

    @function_tool
    async def check_time_window(context: RunContext, day: str, part_of_day: PartOfDay) -> str:
        """Prüft einen Wunschtag, bevor du ihn aufnimmst.

        day: Datum im Format JJJJ-MM-TT. part_of_day: morning (vormittags),
        afternoon (nachmittags) oder any (egal).
        """
        try:
            result = await api.check_time_window(day, part_of_day.value)
        except ApiRejected as error:
            raise _rejected(error, "Eingabe ungültig.") from None
        except ApiUnavailable as error:
            raise _unavailable(context, error, "check_time_window", report) from None
        if result.get("ok"):
            return "Der Wunschtag passt."
        return f"Der Wunschtag passt nicht: {result.get('reason', '')}"

    @function_tool
    async def create_phone_request(
        context: RunContext,
        appointment_type_id: int,
        first_name: str,
        last_name: str,
        date_of_birth: str,
        is_existing_patient: bool,
        insurance: Insurance,
        phone: str,
        time_windows: list[TimeWindow],
        email: str | None = None,
        contact_name: str | None = None,
        contact_relationship: str | None = None,
    ) -> str:
        """Legt die Terminanfrage an, erst nach bestätigter Zusammenfassung.

        appointment_type_id: id aus get_practice_info(appointment_types).
        date_of_birth und time_windows[].date im Format JJJJ-MM-TT, ein bis
        drei Wunschtage. insurance: statutory (gesetzlich), private (privat)
        oder self_pay (selbst). email nur, wenn genannt. contact_name und
        contact_relationship nur, wenn jemand für eine andere Person anruft,
        dann beide.
        """
        if call["create_failed"]:
            # The request may have been stored before the failure; a second
            # try in the same call could create it twice.
            raise _unavailable(
                context, ApiUnavailable("schon gescheitert"), "create_phone_request", report
            )
        if call["created"] >= MAX_REQUESTS_PER_CALL:
            raise ToolError(
                "In einem Anruf nehme ich höchstens drei Anfragen auf. "
                "Weitere bitte später oder direkt mit dem Praxisteam."
            )
        data = {
            "appointment_type": appointment_type_id,
            "patient_first_name": first_name,
            "patient_last_name": last_name,
            "patient_date_of_birth": date_of_birth,
            "is_existing_patient": is_existing_patient,
            "insurance_type": insurance.value,
            "phone": phone,
            "email": email or "",
            "contact_name": contact_name or "",
            "contact_relationship": contact_relationship or "",
            "time_windows": [
                {"date": w.date, "part_of_day": w.part_of_day.value} for w in time_windows
            ],
            "privacy_notice_version": texts.NOTICE_VERSION,
        }
        try:
            reference = await api.create_request(data)
        except ApiRejected as error:
            raise _rejected(error, "Nicht angelegt.") from None
        except ApiUnavailable as error:
            call["create_failed"] = True
            raise _unavailable(context, error, "create_phone_request", report) from None
        call["created"] += 1
        report.request_created(reference)
        return f"Angelegt. Kennung zum Vorlesen: {spell(reference)}"

    @function_tool
    async def create_callback_request(
        context: RunContext,
        name: str,
        phone: str,
        category: CallbackCategory,
        reference: str | None = None,
    ) -> str:
        """Legt eine Rückrufbitte an, erst nach bestätigter Zusammenfassung.

        name: Name der Person, die zurückgerufen werden soll. phone:
        Rückrufnummer. category: prescription (Rezept), referral
        (Überweisung), sick_note (Krankschreibung), findings (Befund),
        doctor_callback (Rückruf der Ärztin bzw. des Arztes), cancel_or_move
        (Termin absagen oder verschieben), other (Sonstiges). reference nur
        bei cancel_or_move und nur, wenn die Kennung der Anfrage genannt wird.
        Keine weiteren Angaben, keinen Grund, keine Medikamente.
        """
        if call["callback_failed"]:
            # As with requests: it may have been stored before the failure.
            raise _unavailable(
                context, ApiUnavailable("schon gescheitert"), "create_callback_request", report
            )
        if call["callbacks"] >= MAX_CALLBACKS_PER_CALL:
            raise ToolError(
                "In einem Anruf nehme ich höchstens drei Rückrufbitten auf. "
                "Weitere bitte direkt mit dem Praxisteam."
            )
        data = {"name": name, "phone": phone, "category": category.value}
        if reference:
            data["reference"] = reference
        try:
            callback_id = await api.create_callback(data)
        except ApiRejected as error:
            raise _rejected(error, "Nicht angelegt.") from None
        except ApiUnavailable as error:
            call["callback_failed"] = True
            raise _unavailable(context, error, "create_callback_request", report) from None
        call["callbacks"] += 1
        report.callback_created(callback_id)
        return "Angelegt. Das Praxisteam ruft zurück."

    return [get_practice_info, check_time_window, create_phone_request, create_callback_request]
