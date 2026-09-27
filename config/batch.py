"""Runs of the system over many records (#9).

The apps provide the runs, the worker in `jobs` calls them. One broken
record must not stop the others: `each` handles every record on its own and
reports failures at the end as `PartialFailure`. It lives here, not in
`jobs`, because the apps must not depend on the worker.
"""

from collections.abc import Callable, Iterable


class PartialFailure(Exception):
    """Some records failed; the others are done.

    `error` names what went wrong without any values: an exception class or a
    fixed text such as the kind of an undelivered mail. It goes into the log
    and into the alert mail.
    """

    def __init__(self, processed: int, failed: int, error: str):
        super().__init__(error)
        self.processed = processed
        self.failed = failed
        self.error = error


def each(ids: Iterable, handle: Callable[[object], bool]) -> int:
    """Call `handle` for every id; count those it returns True for.

    `handle` opens its own transaction, so a failure rolls back only its record.
    """
    processed = failed = 0
    error = ""
    for pk in ids:
        try:
            if handle(pk):
                processed += 1
        except Exception as exc:  # one record must not stop the run
            failed += 1
            # Only the class: the message may contain an address or a name.
            error = error or type(exc).__name__
    if failed:
        raise PartialFailure(processed, failed, error)
    return processed
