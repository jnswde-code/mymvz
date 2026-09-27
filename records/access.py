"""The one check who may read and write the record (#23 section 5, #37, #38, #39).

Every view, search, export and later voice control (#16) reads the record
through `visible_to` or `can_view`; no code reads it past this module.
`can_view` is `visible_to` on one row, so both always agree. Whatever is not
defined here stays closed.

Two layers (#23 section 5): whose chart someone sees, and which protection
levels in it.
- Patients: doctors and MFA see every patient (`view_all_patients`), the
  other professions only those whose care team they are on today
  (`patients.CareTeamMember`, `patients.models.valid_on`). A patient with a
  restriction (`Patient.is_restricted`) only those released for it or with a
  running emergency access (`patients.models.restriction_open`), on top.
- Levels: `normal` for everyone who sees the chart. `addiction` for doctors
  and addiction therapy (`view_addiction`); MFA see it only as a placeholder
  until K4 brings the dispensing data (#27, question 7). `psychotherapy`
  only for the treating person, the author of the first version of the
  lineage, as long as they may still write it. `restricted` for the author
  likewise, and for those the restriction of the patient is open to (release
  or emergency access). A consent (`patients.ConsentToShare`) opens an area
  of one patient to a named person on top of that; the person still needs
  the chart and the care team.

Roles come as Django permissions (`accounts/roles.py`):
- `records.view_chartentry`: read the chart,
- `records.view_all_patients`: every patient, without a care team,
- `records.view_addiction`: entries of the level `addiction`,
- `records.add_chartentry`: write contacts and entries, and correct or mark
  as error one's own,
- `records.write_<level>`: which levels one's entries may have
  (`write_restricted`: doctors),
- `records.change_chartentry`: correct or mark as error anyone's (doctors),
- `records.view_entered_in_error`: see what was marked as error (doctors,
  each view logged; #23 section 3.1).
"""

from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone

from patients.models import (
    CareTeamMember,
    ConsentToShare,
    can_see_patient,
    is_on_care_team,
    restriction_open,
    valid_on,
)
from records.models import ChartEntry, Encounter, Sensitivity, Status

VIEW = "records.view_chartentry"
WRITE = "records.add_chartentry"
CHANGE_ANY = "records.change_chartentry"
VIEW_ERRORS = "records.view_entered_in_error"
ALL_PATIENTS = "records.view_all_patients"
VIEW_ADDICTION = "records.view_addiction"
WRITE_LEVEL = {
    Sensitivity.NORMAL: "records.write_normal",
    Sensitivity.ADDICTION: "records.write_addiction",
    Sensitivity.PSYCHOTHERAPY: "records.write_psychotherapy",
    Sensitivity.RESTRICTED: "records.write_restricted",
}

# The order decides the default in the form: the first one the user may
# write, so psychology starts with psychotherapy (#38).
OPEN_SENSITIVITIES = (
    Sensitivity.NORMAL,
    Sensitivity.ADDICTION,
    Sensitivity.PSYCHOTHERAPY,
    Sensitivity.RESTRICTED,
)


def has_chart_role(user) -> bool:
    """May read the chart of some patient; which ones, `can_view_chart` says."""
    return bool(user.is_active and user.has_perm(VIEW))


def _team_patients(user, day):
    return CareTeamMember.objects.filter(valid_on(day), user=user).values("patient_id")


def _consent_patients(user, area, day):
    return ConsentToShare.objects.filter(valid_on(day), user=user, area=area).values("patient_id")


def is_locked(user, patient) -> bool:
    """A restriction closes this patient for the user (#39); the lock page shows the way past."""
    return not can_see_patient(user, patient)


def can_view_chart(user, patient) -> bool:
    if not has_chart_role(user) or is_locked(user, patient):
        return False
    return user.has_perm(ALL_PATIENTS) or is_on_care_team(user, patient)


def writable_sensitivities(user) -> list:
    """The levels the user's entries may have, in the order of `OPEN_SENSITIVITIES`."""
    if not (user.is_active and user.has_perm(WRITE)):
        return []
    return [level for level in OPEN_SENSITIVITIES if user.has_perm(WRITE_LEVEL[level])]


def can_write(user, patient) -> bool:
    return can_view_chart(user, patient) and bool(writable_sensitivities(user))


def can_view_errors(user) -> bool:
    return has_chart_role(user) and user.has_perm(VIEW_ERRORS)


def _own(user, model) -> Q:
    """The user wrote the first version of the lineage."""
    return Q(
        Exists(model.objects.filter(lineage_id=OuterRef("lineage_id"), version=1, recorded_by=user))
    )


def _levels(user, model, now, released) -> Q:
    """The protection levels the user may read, as a filter on `model`.

    `released`: the patients whose restriction is open to the user.
    """
    day = timezone.localdate(now)
    allowed = Q(sensitivity=Sensitivity.NORMAL)
    addiction = Q(sensitivity=Sensitivity.ADDICTION)
    if not user.has_perm(VIEW_ADDICTION):
        addiction &= Q(patient_id__in=_consent_patients(user, Sensitivity.ADDICTION, day))
    shared = Q(patient_id__in=_consent_patients(user, Sensitivity.PSYCHOTHERAPY, day))
    if user.has_perm(WRITE_LEVEL[Sensitivity.PSYCHOTHERAPY]):
        shared |= _own(user, model)
    psychotherapy = Q(sensitivity=Sensitivity.PSYCHOTHERAPY) & shared
    # An emergency access opens restricted entries too, psychotherapy never.
    if user.has_perm(WRITE_LEVEL[Sensitivity.RESTRICTED]):
        released |= _own(user, model)
    restricted = Q(sensitivity=Sensitivity.RESTRICTED) & released
    return allowed | addiction | psychotherapy | restricted


def visible_to(user, queryset, *, include_errors: bool = False):
    """The versions of `queryset` the user may read.

    A lineage whose head is `entered_in_error` is hidden with all its
    versions; with `include_errors` it is shown to those who may see it.
    """
    if not has_chart_role(user):
        return queryset.none()
    now = timezone.now()
    released = restriction_open(user, "patient_id", now)
    visible = queryset.filter(Q(patient__is_restricted=False) | released)
    if not user.has_perm(ALL_PATIENTS):
        visible = visible.filter(patient_id__in=_team_patients(user, timezone.localdate(now)))
    visible = visible.filter(_levels(user, queryset.model, now, released))
    if not (include_errors and can_view_errors(user)):
        in_error = queryset.model.objects.filter(
            lineage_id=OuterRef("lineage_id"), status=Status.ENTERED_IN_ERROR
        )
        visible = visible.exclude(Exists(in_error))
    return visible


def can_view(user, record, *, include_errors: bool = False) -> bool:
    queryset = type(record).objects.filter(pk=record.pk)
    return visible_to(user, queryset, include_errors=include_errors).exists()


def hidden_entries(user, patient) -> dict:
    """Active entries of the chart the user may not read: their number per contact lineage.

    For the placeholder "n Einträge mit Zugriffsbeschränkung" (#23 decision 7):
    only a number, nothing about level, author, type or text.
    """
    heads = ChartEntry.objects.filter(patient=patient, status=Status.ACTIVE)
    hidden = heads.exclude(pk__in=visible_to(user, heads).values("pk"))
    counts = hidden.order_by().values("encounter_lineage_id").annotate(n=Count("pk"))
    return {row["encounter_lineage_id"]: row["n"] for row in counts}


def hides_restricted(user, patient) -> bool:
    """Some active entry with the level `restricted` is hidden from the user.

    Only these an emergency access would open (#39), so only then the chart
    offers it; psychotherapy stays closed either way.
    """
    heads = ChartEntry.objects.filter(
        patient=patient, status=Status.ACTIVE, sensitivity=Sensitivity.RESTRICTED
    )
    return heads.exclude(pk__in=visible_to(user, heads).values("pk")).exists()


def can_change(user, record) -> bool:
    """Correct or mark as error (#27, open question 2).

    The author of the lineage and doctors may, as long as it is active and
    they may write its level; afterwards an error is visible to doctors only.
    """
    return record.lineage_id in changeable(user, [record])


def changeable(user, records) -> set:
    """`can_change` for many heads of one model at once: their lineage ids the user may change."""
    records = [r for r in records if r.status == Status.ACTIVE]
    if not records or not (user.is_active and user.has_perm(WRITE)):
        return set()
    model = type(records[0])
    heads = model.objects.filter(pk__in=[r.pk for r in records], status=Status.ACTIVE)
    candidates = visible_to(user, heads)
    # A contact is the frame for entries of every level; whoever writes
    # entries may keep their own contacts right.
    if model is not Encounter:
        candidates = candidates.filter(sensitivity__in=writable_sensitivities(user))
    own = _own(user, model)
    if user.has_perm(CHANGE_ANY):
        # A consent opens psychotherapy for reading only; someone else's
        # notes stay the treating person's to correct.
        candidates = candidates.filter(~Q(sensitivity=Sensitivity.PSYCHOTHERAPY) | own)
    else:
        candidates = candidates.filter(own)
    return set(candidates.values_list("lineage_id", flat=True))
