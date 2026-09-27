"""The worker: a loop that runs the due jobs every 15 seconds (#9, decision 1).

Only one worker at a time: a PostgreSQL advisory lock. A second one (e.g.
during a deploy) waits instead of sending mails twice. SIGTERM lets the
current pass finish, then the loop ends; `docker compose stop` waits for it.
"""

import logging
import signal
import threading

from django.core.management.base import BaseCommand
from django.db import connection

from jobs import runner

logger = logging.getLogger("jobs")

# Any fixed number (here the issue, #9); it names the worker's lock in PostgreSQL.
LOCK_KEY = 909


def hold_lock() -> bool:
    """Take the lock unless this connection holds it already.

    It belongs to the database session: after a lost connection it is gone,
    so every pass checks it again.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM pg_locks WHERE locktype = 'advisory' AND classid = 0"
            " AND objid = %s AND objsubid = 1 AND pid = pg_backend_pid() AND granted",
            [LOCK_KEY],
        )
        if cursor.fetchone():
            return True
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [LOCK_KEY])
        return cursor.fetchone()[0]


class Command(BaseCommand):
    help = "Startet den Worker: Postausgang, Verfall von Vorschlägen und Anfragen."

    def handle(self, *args, **options):
        stop = threading.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: stop.set())
        logger.info("Worker gestartet")
        waiting = False
        while not stop.is_set():
            try:
                if hold_lock():
                    if waiting:
                        logger.info("Sperre erhalten, Worker arbeitet")
                        waiting = False
                    runner.run_pass()
                elif not waiting:
                    logger.info("Ein anderer Worker läuft, dieser wartet")
                    waiting = True
            except Exception as exc:  # e.g. the database restarts
                logger.error("Durchgang fehlgeschlagen: %s", type(exc).__name__)
                # A broken connection is replaced on the next query; the lock
                # is taken again there.
                connection.close()
            stop.wait(runner.PASS_INTERVAL)
        logger.info("Worker beendet")
