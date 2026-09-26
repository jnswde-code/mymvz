from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from audit.log import log_access
from audit.models import AccessLogEntry


@login_required
@permission_required("audit.view_accesslogentry", raise_exception=True)
@never_cache
def log_view(request):
    """Read-only list for the administration (data protection, #23 5.1)."""
    log_access(request.user, "list", AccessLogEntry)
    entries = AccessLogEntry.objects.select_related("user")
    page = Paginator(entries, 50).get_page(request.GET.get("seite"))
    return render(request, "audit/log.html", {"page": page})
