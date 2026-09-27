"""The team's list of callbacks under /rueckrufe/ (#45).

Kept apart from the internal API (`api.py`), which authenticates by key:
here every view needs a role, doctors and MFA as for requests (#8,
decision 1). The role first, then the service reads and logs. Ticking off
is a POST; one that was ticked off meanwhile becomes a message, not a 500.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from telephony import services

VIEW = "telephony.view_callbackrequest"
CHANGE = "telephony.change_callbackrequest"


@login_required
@permission_required(VIEW, raise_exception=True)
@never_cache
@require_GET
def list_view(request):
    return render(
        request,
        "telephony/staff/callbacks.html",
        {
            "callbacks": services.list_callbacks(request.user),
            "expires_after_days": services.CALLBACK_EXPIRES_AFTER_DAYS,
        },
    )


@login_required
@permission_required(CHANGE, raise_exception=True)
@require_POST
def done_view(request, pk):
    try:
        services.mark_done(pk, actor=request.user)
    except services.NotOpen:
        messages.warning(request, "Diese Rückrufbitte ist schon erledigt.")
    else:
        messages.success(request, "Als erledigt abgehakt.")
    return redirect("telephony:callbacks")
