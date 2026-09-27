from django.db import models


class JobRun(models.Model):
    """One run of one job of the worker (#9).

    Only the job, times and numbers: no ids of records, no names. The last
    run of a job decides when it is due again, and the newest finished run
    tells `worker_health` that the worker is alive.
    """

    job = models.CharField(max_length=40)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    ok = models.BooleanField(null=True)
    processed = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    # Name of the exception or a fixed text, never its message (`PartialFailure`).
    error = models.CharField(max_length=200, blank=True)
    # The operations address was told about this run (at most once per job and day).
    alerted = models.BooleanField(default=False)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "Lauf"
        verbose_name_plural = "Läufe"
        indexes = [
            models.Index(fields=["job", "-started_at"], name="jobs_run_job_started"),
            models.Index(fields=["-finished_at"], name="jobs_run_finished"),
        ]

    def __str__(self):
        return f"{self.job} {self.started_at:%Y-%m-%d %H:%M}"
