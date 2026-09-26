"""Logs without phone numbers and without conversation content (#14, section 6).

The agent itself never logs what callers say. LiveKit does: at debug level
it logs every conversation item with its text, and participant identities,
which for a SIP caller carry the phone number (`sip_+49...`). LiveKit marks
such fields with the prefix `lk.pii.`; the filter replaces them entirely.
Beyond that it blanks out every run of six or more digits, in the message,
its arguments, tracebacks and all other extra fields. It errs on the side
of blanking too much: a lost room id costs nothing, a leaked number does.
"""

from __future__ import annotations

import logging
import re

# A run of at least six digits, optionally with + or 00 in front and single
# blanks, slashes, dashes or brackets in between ("(02181) 47 57 62-0").
# Dots do not join digits, so "0.912 s" stays readable.
_PHONE = re.compile(r"(?<!\d)\(?(?:\+|00)?\d(?:[ /()\-]{0,2}\d){5,}(?!\d)")
REDACTED = "[Nummer entfernt]"
PII_REMOVED = "[entfernt]"
_PII_PREFIX = "lk.pii."

# Attributes every LogRecord has; anything else came in via `extra=`.
_STANDARD = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


def redact(text: str) -> str:
    return _PHONE.sub(REDACTED, text)


def _redact_value(value: object) -> object:
    if isinstance(value, str):
        return redact(value)
    if value is None or isinstance(value, bool | float):
        return value
    # Lists, dicts, ints: checked as text, left as they are when clean.
    text = str(value)
    cleaned = redact(text)
    return value if cleaned == text else cleaned


class RedactPersonalData(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # a broken log call must not break the caller
            message = f"{record.msg} {record.args}"
        record.msg = redact(message)
        record.args = None
        if record.exc_info and not record.exc_text:
            # Formatters reuse exc_text instead of formatting exc_info again.
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        if record.stack_info:
            record.stack_info = redact(record.stack_info)
        for key, value in vars(record).items():
            if key.startswith(_PII_PREFIX):
                setattr(record, key, PII_REMOVED)
            elif key not in _STANDARD:
                setattr(record, key, _redact_value(value))
        return True


def install() -> None:
    """Put the filter on every handler of the root logger, once.

    Called in the worker process once LiveKit has set up its handlers. Job
    processes forward their records to it, and LiveKit adds job fields such
    as the room name only there, just before the handlers; for a SIP call
    the room name contains the phone number. A handler filter sees them,
    a logger filter would not.
    """
    for handler in logging.getLogger().handlers:
        if not any(isinstance(f, RedactPersonalData) for f in handler.filters):
            handler.addFilter(RedactPersonalData())
