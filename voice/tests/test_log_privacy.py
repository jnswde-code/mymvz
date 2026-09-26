"""No phone numbers in logs (#14, section 6). All numbers are made up."""

import logging

import pytest

from mymvz_voice.log_privacy import PII_REMOVED, REDACTED, RedactPersonalData, install, redact


@pytest.mark.parametrize(
    "number",
    [
        "+49 2181 4757620",
        "02181/475762-0",
        "(02181) 47 57 62-0",
        "0172 1234567",
        "004921814757620",
        "123456",
    ],
)
def test_phone_numbers_are_removed(number):
    assert redact(f"Anruf von {number} angenommen") == f"Anruf von {REDACTED} angenommen"


def test_sip_identity_is_removed():
    assert redact("participant sip_+4921814757620 joined") == f"participant sip_{REDACTED} joined"


@pytest.mark.parametrize(
    "text",
    [
        "Port 7880",
        "Latenz 0.912 s",
        "Versuch 3 von 5",
        "PLZ 41515",
        "Zeit 12:30:45",
    ],
)
def test_short_numbers_stay(text):
    assert redact(text) == text


def test_filter_cleans_message_arguments_and_extra_fields():
    record = logging.makeLogRecord(
        {"msg": "Anruf von %s", "args": ("0172 1234567",), "participant": "sip_01721234567"}
    )
    assert RedactPersonalData().filter(record)
    assert record.getMessage() == f"Anruf von {REDACTED}"
    assert record.participant == f"sip_{REDACTED}"


def test_filter_removes_fields_livekit_marks_as_personal():
    """LiveKit logs transcripts as `lk.pii.text` at debug level."""
    record = logging.makeLogRecord(
        {
            "msg": "conversation_item_added",
            "lk.pii.text": "Ich habe Rückenschmerzen",
            "lk.pii.participant_identity": "tester",
            "role": "user",
        }
    )
    RedactPersonalData().filter(record)
    assert vars(record)["lk.pii.text"] == PII_REMOVED
    assert vars(record)["lk.pii.participant_identity"] == PII_REMOVED
    assert record.role == "user"


def test_install_puts_the_filter_on_every_root_handler_once():
    root = logging.getLogger()
    handler = logging.NullHandler()
    root.addHandler(handler)
    try:
        install()
        install()
        assert sum(isinstance(f, RedactPersonalData) for f in handler.filters) == 1
    finally:
        root.removeHandler(handler)
