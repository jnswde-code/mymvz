"""The jobs of the worker and when they are due (#9, sections 2 and 4).

A job is due when its last run started at least one interval ago. So a
restart of the container does not run a daily job twice, and a missed run is
made up on the next pass. The apps provide the functions; `jobs` knows them,
not the other way round.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from appointments import mail, services
from appointments.models import OutgoingMail
from config.batch import PartialFailure
from jobs import alerts
from jobs.models import JobRun

logger = logging.getLogger("jobs")

# Seconds between two passes of the worker.
PASS_INTERVAL = 15
# `worker_health` fails when no run finished within this; the outbox runs every pass.
HEALTHY_WITHIN = timedelta(minutes=5)
# Finished runs and sent mails are kept this long; they hold only kinds and ids.
KEEP_FOR = timedelta(days=30)


def clean_up(now=None) -> int:
    """Delete old runs and sent mails of the outbox."""
    before = (now or timezone.now()) - KEEP_FOR
    runs, _ = JobRun.objects.filter(started_at__lt=before).delete()
    mails, _ = OutgoingMail.objects.filter(sent_at__lt=before).delete()
    return runs + mails


@dataclass(frozen=True)
class Job:
    name: str
    # For the log and the alert mail.
    label: str
    every: timedelta
    run: Callable[[], int]


JOBS = [
    # Every pass: a confirmation link should arrive at once.
    Job("outbox", "Postausgang senden", timedelta(0), mail.process_outbox),
    # The link checks the deadline itself; this only tells the request.
    Job(
        "expire_proposals",
        "Vorschläge verfallen lassen",
        timedelta(minutes=5),
        services.expire_overdue_proposals,
    ),
    # The limit is midnight in Europe/Berlin.
    Job(
        "expire_requests",
        "Anfragen verfallen lassen",
        timedelta(hours=1),
        services.expire_overdue_requests,
    ),
    Job("clean_up", "Alte Läufe und Mails löschen", timedelta(days=1), clean_up),
]


def is_due(job: Job, now) -> bool:
    last = JobRun.objects.filter(job=job.name).order_by("-started_at").first()
    return last is None or last.started_at <= now - job.every


def run_job(job: Job) -> JobRun:
    """Run one job, record it, log one line and alert on failure."""
    run = JobRun.objects.create(job=job.name, started_at=timezone.now())
    began = time.monotonic()
    try:
        run.processed = job.run()
    except PartialFailure as exc:
        run.processed, run.failed, run.error = exc.processed, exc.failed, exc.error[:200]
    except Exception as exc:  # the worker goes on with the next job
        run.failed, run.error = 1, type(exc).__name__
    run.ok = run.failed == 0
    run.finished_at = timezone.now()
    run.save()
    seconds = time.monotonic() - began
    if run.ok:
        if run.processed or job.every:
            logger.info("%s: %d erledigt in %.1f s", job.name, run.processed, seconds)
    else:
        # The kind of error only; a traceback would show values of records.
        logger.error(
            "%s fehlgeschlagen: %d erledigt, %d Fehler (%s) in %.1f s",
            job.name,
            run.processed,
            run.failed,
            run.error,
            seconds,
        )
        alerts.notify(run, job.label)
    return run


def run_pass(now=None) -> list[JobRun]:
    """One pass of the worker: every due job, in the order of `JOBS`."""
    now = now or timezone.now()
    return [run_job(job) for job in JOBS if is_due(job, now)]


def healthy(now=None) -> bool:
    """Whether a run finished within `HEALTHY_WITHIN`."""
    now = now or timezone.now()
    return JobRun.objects.filter(finished_at__gte=now - HEALTHY_WITHIN).exists()
