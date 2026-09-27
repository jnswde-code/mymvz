"""Alert mail to the operations address when a run fails (#9, decision 3).

The mail names the job and the kind of error, nothing else: no record, no
name, no address. Details are in the server's log. At most one mail per job
and day in Europe/Berlin, so a broken job does not send one every pass.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from jobs.models import JobRun

logger = logging.getLogger("jobs")

SUBJECT = "Betriebsmeldung MyMVZ: Lauf fehlgeschlagen"


def _start_of_day(now):
    local = timezone.localtime(now)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def notify(run: JobRun, label: str) -> bool:
    """Send the alert for a failed run unless the job had one today."""
    already = JobRun.objects.filter(
        job=run.job, alerted=True, started_at__gte=_start_of_day(run.started_at)
    ).exists()
    if already:
        return False
    stamp = timezone.localtime(run.finished_at or run.started_at)
    body = (
        f"Der Lauf „{label}“ ist fehlgeschlagen ({run.error}).\n"
        f"Näheres steht im Log des Servers. Stand: {stamp:%d.%m.%Y, %H:%M} Uhr.\n\n"
        "Weitere Fehler dieses Laufs meldet der Worker erst morgen wieder.\n"
    )
    try:
        EmailMessage(SUBJECT, body, to=[settings.OPERATIONS_ALERT_EMAIL]).send()
    except Exception as exc:  # the log still has the failure
        logger.error("Meldung für %s nicht versandt: %s", run.job, type(exc).__name__)
        return False
    run.alerted = True
    run.save(update_fields=["alerted"])
    return True
