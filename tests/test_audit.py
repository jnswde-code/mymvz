"""The access log: type and id, no content (#5, #25)."""

import uuid

import pytest
from django.contrib.auth.models import AnonymousUser, Group
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.urls import reverse

from accounts import roles
from accounts.testing import login_with_second_factor, make_user
from audit.log import log_access
from audit.models import AccessLogEntry

pytestmark = pytest.mark.django_db


def test_entry_has_type_and_id_only():
    user = make_user()
    group = Group.objects.get(name=roles.MFA)
    entry = log_access(user, "view", group)
    assert entry.user == user
    assert entry.action == "view"
    assert entry.object_type == "auth.group"
    assert entry.object_id == str(group.pk)
    assert entry.patient_id is None


def test_fields_leave_no_room_for_content():
    """A new field here needs a reason; names and content never belong in it."""
    assert {f.name for f in AccessLogEntry._meta.get_fields()} == {
        "id",
        "at",
        "user",
        "action",
        "object_type",
        "object_id",
        "patient_id",
        "result_count",
    }


def test_list_and_search_log_the_model():
    user = make_user()
    patient_id = uuid.uuid4()
    entry = log_access(user, "search", Group, result_count=3, patient_id=patient_id)
    assert (entry.object_type, entry.object_id, entry.result_count) == ("auth.group", "", 3)
    assert entry.patient_id == patient_id


def test_unknown_action_is_rejected():
    with pytest.raises(ValueError):
        log_access(make_user(), "peek", Group)


def test_database_rejects_unknown_action():
    with pytest.raises(IntegrityError):
        AccessLogEntry.objects.create(user=make_user(), action="peek", object_type="auth.group")


def test_anonymous_and_unsaved_are_rejected():
    user = make_user()
    with pytest.raises(ValueError):
        log_access(AnonymousUser(), "view", Group)
    with pytest.raises(ValueError):
        log_access(user, "view", Group(name="neu"))
    with pytest.raises(TypeError):
        log_access(user, "view", "auth.group")


def test_entries_are_never_changed():
    entry = log_access(make_user(), "view", Group.objects.first())
    entry.object_id = "anders"
    with pytest.raises(ValueError):
        entry.save()


def test_user_with_entries_cannot_be_removed_by_queryset():
    user = make_user()
    log_access(user, "list", Group)
    with pytest.raises(ProtectedError):
        type(user).objects.filter(pk=user.pk).delete()


def test_log_view_logs_itself(client):
    user = make_user(roles=[roles.ADMINISTRATION])
    login_with_second_factor(client, user)
    client.get(reverse("audit:log"))
    entry = AccessLogEntry.objects.get()
    assert (entry.user, entry.action, entry.object_type) == (
        user,
        "list",
        "audit.accesslogentry",
    )


def test_denied_access_writes_no_entry(client):
    login_with_second_factor(client, make_user(roles=[roles.MFA]))
    assert client.get(reverse("audit:log")).status_code == 403
    assert not AccessLogEntry.objects.exists()


def test_log_pages_from_a_fixed_point_in_time(client):
    user = make_user(roles=[roles.ADMINISTRATION])
    login_with_second_factor(client, user)
    before = log_access(user, "list", Group)
    response = client.get(reverse("audit:log"), {"stand": before.at.isoformat()})
    assert [e.pk for e in response.context["page"]] == [before.pk]


@pytest.mark.parametrize("stand", ["kaputt", "2026-13-45T99:00", "2026-09-26T10:00"])
def test_log_tolerates_odd_points_in_time(client, stand):
    login_with_second_factor(client, make_user(roles=[roles.ADMINISTRATION]))
    assert client.get(reverse("audit:log"), {"stand": stand}).status_code == 200
