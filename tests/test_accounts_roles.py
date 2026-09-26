"""Roles from the data migration, rights also checked negatively (#25)."""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts import roles
from accounts.testing import login_with_second_factor, make_user

pytestmark = pytest.mark.django_db

AUDIT_LOG = reverse("audit:log")


def test_groups_after_migrations_match_roles_module():
    """The migrations carry their own copy of the roles; both must agree."""
    assert set(roles.ROLES.values()) == set(roles.ROLE_PERMISSIONS)
    assert set(Group.objects.values_list("name", flat=True)) == set(roles.ROLE_PERMISSIONS)
    for name, permissions in roles.ROLE_PERMISSIONS.items():
        group = Group.objects.get(name=name)
        granted = {f"{p.content_type.app_label}.{p.codename}" for p in group.permissions.all()}
        assert granted == set(permissions), name


def test_administration_reads_access_log(client):
    login_with_second_factor(client, make_user(roles=[roles.ADMINISTRATION]))
    assert client.get(AUDIT_LOG).status_code == 200


@pytest.mark.parametrize("role", sorted(set(roles.ROLES.values()) - {roles.ADMINISTRATION}))
def test_other_roles_do_not_read_access_log(client, role):
    login_with_second_factor(client, make_user(roles=[role]))
    assert client.get(AUDIT_LOG).status_code == 403


def test_account_without_role_reads_nothing(client):
    login_with_second_factor(client, make_user())
    assert client.get(AUDIT_LOG).status_code == 403


def test_anonymous_is_sent_to_login(client):
    response = client.get(AUDIT_LOG)
    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))
