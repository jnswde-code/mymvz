from django.db import models


class RequestStatistic(models.Model):
    """Counts without any personal reference, for evaluations (#5 section 6, #17).

    The deletion run (#9) adds one to the matching row in the same
    transaction in which it deletes a request. No date of birth, no age
    group, no name, no id: what is counted here is anonymous and may stay.
    """

    class Outcome(models.TextChoices):
        UNVERIFIED = "unverified", "E-Mail nicht bestätigt"
        BOOKED = "booked", "Termin wahrgenommen oder vergeben"
        DECLINED = "declined", "abgelehnt"
        WITHDRAWN = "withdrawn", "zurückgezogen"
        EXPIRED = "expired", "verfallen"
        CANCELLED_BY_PATIENT = "cancelled_by_patient", "vom Patienten abgesagt"
        CANCELLED_BY_PRACTICE = "cancelled_by_practice", "von der Praxis abgesagt"

    class LeadTime(models.TextChoices):
        """Days from request to appointment, in steps."""

        NONE = "", "kein Termin"
        UP_TO_2 = "0-2", "bis 2 Tage"
        UP_TO_7 = "3-7", "3 bis 7 Tage"
        UP_TO_14 = "8-14", "8 bis 14 Tage"
        LONGER = "15+", "mehr als 14 Tage"

    # Monday of the calendar week the request came in.
    week = models.DateField()
    appointment_type = models.ForeignKey(
        "appointments.AppointmentType", on_delete=models.PROTECT, related_name="+"
    )
    channel = models.CharField(max_length=20)
    outcome = models.CharField(max_length=32, choices=Outcome)
    lead_time = models.CharField(max_length=8, choices=LeadTime, blank=True)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["week"]
        verbose_name = "Zählerstand"
        verbose_name_plural = "Zählerstände"
        constraints = [
            models.UniqueConstraint(
                fields=["week", "appointment_type", "channel", "outcome", "lead_time"],
                name="reporting_statistic_one_row_per_group",
            ),
        ]

    def __str__(self):
        return f"{self.week} {self.outcome}: {self.count}"
