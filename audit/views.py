from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache

from audit.log import log_access
from audit.models import AccessLogEntry
from patients.models import EmergencyAccess


def _as_of(value):
    try:
        as_of = parse_datetime(value)
    except ValueError:
        as_of = None
    if as_of is None:
        return timezone.now()
    return as_of if timezone.is_aware(as_of) else timezone.make_aware(as_of)


@login_required
@permission_required("audit.view_accesslogentry", raise_exception=True)
@never_cache
def log_view(request):
    """Read-only list for the administration (data protection, #23 5.1)."""
    # Every page view adds an entry on top. Paging from a fixed point in time
    # keeps rows from sliding onto the next page.
    as_of = _as_of(request.GET.get("stand", ""))
    entries = AccessLogEntry.objects.filter(at__lte=as_of).select_related("user")
    page = Paginator(entries, 50).get_page(request.GET.get("seite"))
    log_access(request.user, "list", AccessLogEntry)
    return render(request, "audit/log.html", {"page": page, "as_of": as_of.isoformat()})


@login_required
@permission_required("patients.view_emergencyaccess", raise_exception=True)
@never_cache
def emergency_list_view(request):
    """Every emergency access with its reason, for the administration (#23 5.2, #39).

    The one place besides the released persons where the reason is shown;
    the access log has only the entry `emergency_access` without it.
    """
    as_of = _as_of(request.GET.get("stand", ""))
    accesses = EmergencyAccess.objects.filter(valid_from__lte=as_of).select_related(
        "user", "patient"
    )
    page = Paginator(accesses, 50).get_page(request.GET.get("seite"))
    log_access(request.user, "list", EmergencyAccess)
    return render(request, "audit/emergency_list.html", {"page": page, "as_of": as_of.isoformat()})
