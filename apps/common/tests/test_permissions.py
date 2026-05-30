"""Unit tests for custom DRF permission classes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from apps.common.permissions import (
    IsOrgAdmin,
    IsOrgManager,
    IsOrgMember,
    IsOrgOwner,
    IsSuperAdminFromAllowedIP,
)

# * helpers


def _make_request(
    is_authenticated: bool = True,
    is_staff: bool = False,
    remote_addr: str = "127.0.0.1",
    forwarded_for: str | None = None,
    org_roles: dict[str, str] | None = None,
    data: dict | None = None,
    query_params: dict | None = None,
) -> MagicMock:
    """Build a minimal fake DRF request."""
    request = MagicMock()
    request.user.is_authenticated = is_authenticated
    request.user.is_staff = is_staff
    request.META = {"REMOTE_ADDR": remote_addr}
    if forwarded_for:
        request.META["HTTP_X_FORWARDED_FOR"] = forwarded_for
    # simulate org_roles via user attribute
    request.user.org_roles = org_roles or {}
    # token without .payload so _get_org_roles falls through to user.org_roles
    request.user.token = None
    request.data = data or {}
    request.query_params = query_params or {}
    return request


def _make_view(kwargs: dict | None = None, org_id: str | None = None) -> MagicMock:
    """Build a minimal fake DRF view."""
    view = MagicMock()
    view.kwargs = kwargs or {}
    if org_id is not None:
        view.org_id = org_id
    else:
        del view.org_id  # ensure getattr falls through
    return view


# * IsSuperAdminFromAllowedIP tests


def test_super_admin_unauthenticated_denied():
    """Unauthenticated requests are always rejected."""
    perm = IsSuperAdminFromAllowedIP()
    req = _make_request(is_authenticated=False)
    assert perm.has_permission(req, MagicMock()) is False


def test_super_admin_non_staff_denied():
    """Authenticated but non-staff users are rejected."""
    perm = IsSuperAdminFromAllowedIP()
    req = _make_request(is_authenticated=True, is_staff=False)
    assert perm.has_permission(req, MagicMock()) is False


def test_super_admin_staff_no_ip_list_allowed(settings):
    """Staff user passes when SUPERADMIN_ALLOWED_IPS is empty (open by default)."""
    settings.SUPERADMIN_ALLOWED_IPS = []
    perm = IsSuperAdminFromAllowedIP()
    req = _make_request(is_staff=True)
    assert perm.has_permission(req, MagicMock()) is True


def test_super_admin_staff_ip_allowed(settings):
    """Staff user on the allowlist passes."""
    settings.SUPERADMIN_ALLOWED_IPS = ["10.0.0.1"]
    perm = IsSuperAdminFromAllowedIP()
    req = _make_request(is_staff=True, remote_addr="10.0.0.1")
    assert perm.has_permission(req, MagicMock()) is True


def test_super_admin_staff_ip_rejected(settings):
    """Staff user NOT on the allowlist is rejected."""
    settings.SUPERADMIN_ALLOWED_IPS = ["10.0.0.1"]
    perm = IsSuperAdminFromAllowedIP()
    req = _make_request(is_staff=True, remote_addr="192.168.1.1")
    assert perm.has_permission(req, MagicMock()) is False


def test_super_admin_uses_first_forwarded_ip(settings):
    """When X-Forwarded-For is present the first IP is used."""
    settings.SUPERADMIN_ALLOWED_IPS = ["10.0.0.2"]
    perm = IsSuperAdminFromAllowedIP()
    req = _make_request(is_staff=True, forwarded_for="10.0.0.2, 10.0.0.99")
    assert perm.has_permission(req, MagicMock()) is True


# * IsOrgRole subclass tests


@pytest.mark.parametrize(
    "perm_class,role,expected",
    [
        (IsOrgOwner, "owner", True),
        (IsOrgOwner, "admin", False),
        (IsOrgOwner, "manager", False),
        (IsOrgOwner, "member", False),
        (IsOrgAdmin, "owner", True),
        (IsOrgAdmin, "admin", True),
        (IsOrgAdmin, "manager", False),
        (IsOrgAdmin, "member", False),
        (IsOrgManager, "owner", True),
        (IsOrgManager, "admin", True),
        (IsOrgManager, "manager", True),
        (IsOrgManager, "member", False),
        (IsOrgMember, "owner", True),
        (IsOrgMember, "admin", True),
        (IsOrgMember, "manager", True),
        (IsOrgMember, "member", True),
    ],
)
def test_org_role_permission_matrix(perm_class, role, expected):
    """Every (class, role) combo grants or denies access correctly."""
    org_id = "org-123"
    perm = perm_class()
    req = _make_request(org_roles={org_id: role}, data={"organization_id": org_id})
    view = _make_view()
    assert perm.has_permission(req, view) is expected


def test_org_role_no_org_id_in_any_source_denied():
    """Permission denied when org_id cannot be found anywhere."""
    perm = IsOrgAdmin()
    req = _make_request(org_roles={"org-abc": "admin"})
    view = _make_view()
    assert perm.has_permission(req, view) is False


def test_org_role_org_id_from_view_kwargs():
    """Org ID resolved from view.kwargs['org_id']."""
    org_id = "org-kwarg"
    perm = IsOrgAdmin()
    req = _make_request(org_roles={org_id: "admin"})
    view = _make_view(kwargs={"org_id": org_id})
    assert perm.has_permission(req, view) is True


def test_org_role_org_id_from_query_params():
    """Org ID resolved from query param when not in data or kwargs."""
    org_id = "org-qp"
    perm = IsOrgMember()
    req = _make_request(org_roles={org_id: "member"}, query_params={"organization_id": org_id})
    view = _make_view()
    assert perm.has_permission(req, view) is True


def test_org_roles_from_jwt_token_payload():
    """org_roles are read from token.payload when available."""
    org_id = "org-jwt"
    perm = IsOrgOwner()
    req = _make_request(data={"organization_id": org_id})
    # simulate token with payload attribute
    token = MagicMock()
    token.payload = {"org_roles": {org_id: "owner"}}
    req.user.token = token
    view = _make_view()
    assert perm.has_permission(req, view) is True
