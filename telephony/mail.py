"""Mail to the practice about new callbacks (#45).

Only that something is new and the address of the list: no name, no number,
no category (#3 section 2). Its own function, apart from the outbox of
`appointments.mail`, which belongs to requests; the worker calls it through
`services.notify_new_callbacks`.
"""

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.urls import reverse

SUBJECT = "Neue Rückrufbitte"


def send_new_callbacks() -> None:
    body = render_to_string(
        "telephony/mail/new_callbacks.txt",
        {"list_url": settings.SITE_BASE_URL + reverse("telephony:callbacks")},
    )
    EmailMessage(SUBJECT, body, to=[settings.PRACTICE_NOTIFICATION_EMAIL]).send()
