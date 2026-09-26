"""Logs without phone numbers and without conversation content (#14, section 6).

The agent itself never logs what callers say. LiveKit does: at debug level
it logs every conversation item with its text, and participant identities,
which for a SIP caller carry the phone number (`sip_+49...`). LiveKit marks
such fields with the prefix `lk.pii.`; the filter replaces them entirely.
Beyond that it blanks out every run of six or more digits, in the message,
its arguments and all other extra fields. It errs on the side of blanking
too much: a lost room id costs nothing, a leaked number does.
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
    return redact(value) if isinstance(value, str) else value


class RedactPersonalData(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        for key, value in vars(record).items():
            if key.startswith(_PII_PREFIX):
                setattr(record, key, PII_REMOVED)
            elif key not in _STANDARD:
                setattr(record, key, _redact_value(value))
        return True


def install() -> None:
    """Put the filter on every handler of the root logger.

    Called at the start of each job, after LiveKit has set up its handlers
    (in the job process they forward records to the worker process, so
    they leave already cleaned).
    """
    for handler in logging.getLogger().handlers:
        if not any(isinstance(f, RedactPersonalData) for f in handler.filters):
            handler.addFilter(RedactPersonalData())
