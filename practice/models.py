from datetime import time

from django.db import models

# Morning ends and afternoon begins here. A consultation block counts for
# the morning if it starts before, for the afternoon if it ends after (#7).
MIDDAY = time(13, 0)


class Resource(models.Model):
    """Who or what an appointment needs (#5, decision 9).

    Stage 1 only uses doctors; rooms and devices (e.g. the TPS device) come
    with the practice calendar. Resources are deactivated, never deleted.
    """

    class Kind(models.TextChoices):
        DOCTOR = "doctor", "Ärztin/Arzt"
        ROOM = "room", "Raum"
        DEVICE = "device", "Gerät"

    kind = models.CharField(max_length=16, choices=Kind)
    # Shown to patients, e.g. "Dr. med. Erika Beispiel".
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Ressource"
        verbose_name_plural = "Ressourcen"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=["doctor", "room", "device"]),
                name="practice_resource_kind_valid",
            ),
        ]

    def __str__(self):
        return self.name


class OpeningHoursQuerySet(models.QuerySet):
    def consultation(self):
        return self.filter(kind=OpeningHours.Kind.CONSULTATION)

    def covers(self, day, part_of_day) -> bool:
        """Whether there is consultation on `day` in `part_of_day`.

        `part_of_day` is "morning", "afternoon" or "any".
        """
        blocks = self.consultation().filter(weekday=day.weekday())
        if part_of_day == "morning":
            blocks = blocks.filter(opens__lt=MIDDAY)
        elif part_of_day == "afternoon":
            blocks = blocks.filter(closes__gt=MIDDAY)
        elif part_of_day != "any":
            raise ValueError(f"Unbekannte Tageszeit: {part_of_day!r}")
        return blocks.exists()


class OpeningHours(models.Model):
    """One block of opening or consultation hours on a weekday (#5).

    The single source for the opening hours shown to patients, the check of
    requested time windows (#7) and, later, consultation blocks (#5 section 5).
    """

    class Kind(models.TextChoices):
        OPENING = "opening", "geöffnet"
        CONSULTATION = "consultation", "Sprechzeit"

    kind = models.CharField(max_length=16, choices=Kind)
    # Monday is 0, as in date.weekday().
    weekday = models.PositiveSmallIntegerField()
    opens = models.TimeField()
    closes = models.TimeField()

    objects = OpeningHoursQuerySet.as_manager()

    class Meta:
        ordering = ["kind", "weekday", "opens"]
        verbose_name = "Öffnungszeit"
        verbose_name_plural = "Öffnungszeiten"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=["opening", "consultation"]),
                name="practice_openinghours_kind_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(weekday__lte=6), name="practice_openinghours_weekday_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(closes__gt=models.F("opens")),
                name="practice_openinghours_closes_after_opens",
            ),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} {self.weekday} {self.opens:%H:%M}–{self.closes:%H:%M}"
