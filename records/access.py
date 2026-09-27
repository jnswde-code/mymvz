"""The one check who may read and write the record (#23 section 5, #37).

Every view, search, export and later voice control (#16) reads the record
through `visible_to` or `can_view`; no code reads it past this module.
`can_view` is `visible_to` on one row, so both always agree.

K2.1 opens the chart to doctors and MFA only (#23 section 5.1: MFA reads and
writes own entries). Every other role, and every protection level other than
`normal`, is refused until K2.2 and K2.3 define them. Whatever is not
defined here stays closed.

Roles come as Django permissions (`accounts/roles.py`):
- `records.view_chartentry`: read the chart (contacts and entries),
- `records.add_chartentry`: write contacts and entries, and correct or mark
  as error one's own,
- `records.change_chartentry`: correct or mark as error anyone's (doctors),
- `records.view_entered_in_error`: see what was marked as error (doctors,
  each view logged; #23 section 3.1).
"""

from django.db.models import Exists, OuterRef

from records.models import Sensitivity, Status

VIEW = "records.view_chartentry"
WRITE = "records.add_chartentry"
CHANGE_ANY = "records.change_chartentry"
VIEW_ERRORS = "records.view_entered_in_error"

# Protection levels that can be read and written today (K2.2 adds addiction
# and psychotherapy, K2.3 restricted).
OPEN_SENSITIVITIES = (Sensitivity.NORMAL,)


def can_view_chart(user, patient) -> bool:
    return bool(user.is_active and user.has_perm(VIEW))


def can_write(user, patient) -> bool:
    return can_view_chart(user, patient) and user.has_perm(WRITE)


def can_view_errors(user) -> bool:
    return can_view_chart(user, None) and user.has_perm(VIEW_ERRORS)


def visible_to(user, queryset, *, include_errors: bool = False):
    """The versions of `queryset` the user may read.

    A lineage whose head is `entered_in_error` is hidden with all its
    versions; with `include_errors` it is shown to those who may see it.
    """
    if not can_view_chart(user, None):
        return queryset.none()
    visible = queryset.filter(sensitivity__in=OPEN_SENSITIVITIES)
    if not (include_errors and can_view_errors(user)):
        in_error = queryset.model.objects.filter(
            lineage_id=OuterRef("lineage_id"), status=Status.ENTERED_IN_ERROR
        )
        visible = visible.exclude(Exists(in_error))
    return visible


def can_view(user, record, *, include_errors: bool = False) -> bool:
    queryset = type(record).objects.filter(pk=record.pk)
    return visible_to(user, queryset, include_errors=include_errors).exists()


def can_change(user, record) -> bool:
    """Correct or mark as error (#27, open question 2).

    The author of the lineage and doctors may, as long as it is active;
    afterwards an error is visible to doctors only.
    """
    return record.lineage_id in changeable(user, [record])


def changeable(user, records) -> set:
    """`can_change` for many heads of one model at once: their lineage ids the user may change."""
    records = [r for r in records if r.status == Status.ACTIVE]
    if not records or not can_write(user, None):
        return set()
    model = type(records[0])
    heads = model.objects.filter(pk__in=[r.pk for r in records], status=Status.ACTIVE)
    candidates = visible_to(user, heads)
    if not user.has_perm(CHANGE_ANY):
        own = model.objects.filter(lineage_id=OuterRef("lineage_id"), version=1, recorded_by=user)
        candidates = candidates.filter(Exists(own))
    return set(candidates.values_list("lineage_id", flat=True))
