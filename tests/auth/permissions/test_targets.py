"""Tests for the shared device, area, and domain permission resolver."""

import pytest

from homeassistant.auth.permissions import (
    POLICY_SCHEMA,
    OwnerPermissions,
    PolicyPermissions,
    resolve_target_permission,
)
from homeassistant.auth.permissions.const import (
    POLICY_CONFIGURE,
    POLICY_CONTROL,
    POLICY_EDIT,
    POLICY_READ,
)


@pytest.mark.parametrize(
    ("target_type", "subcategory"),
    [("device", "device_ids"), ("area", "area_ids"), ("domain", "domains")],
)
def test_resolve_target_direct_rule(target_type: str, subcategory: str) -> None:
    """Test the direct rule of every target type grants each right separately."""
    policy = POLICY_SCHEMA(
        {
            "entities": {
                subcategory: {
                    "target-1": {
                        "read": True,
                        "control": True,
                        "edit": True,
                        "configure": True,
                    }
                }
            }
        }
    )
    assert (
        resolve_target_permission(policy, target_type, "target-1", POLICY_READ) is True
    )
    assert (
        resolve_target_permission(policy, target_type, "target-1", POLICY_CONTROL)
        is True
    )
    assert (
        resolve_target_permission(policy, target_type, "target-1", POLICY_EDIT) is True
    )
    assert (
        resolve_target_permission(policy, target_type, "target-1", POLICY_CONFIGURE)
        is True
    )
    assert (
        resolve_target_permission(policy, target_type, "target-2", POLICY_READ) is False
    )


@pytest.mark.parametrize("target_type", ["device", "area", "domain"])
def test_resolve_target_missing_right_falls_through_to_all(target_type: str) -> None:
    """Test a rule without an opinion falls through to the all rule."""
    policy = POLICY_SCHEMA(
        {
            "entities": {
                "all": {"read": True},
            }
        }
    )
    assert (
        resolve_target_permission(policy, target_type, "target-1", POLICY_READ) is True
    )
    assert (
        resolve_target_permission(policy, target_type, "target-1", POLICY_CONTROL)
        is False
    )


def test_resolve_target_true_category_allows_all() -> None:
    """Test a fully open category allows every target."""
    policy = POLICY_SCHEMA({"entities": True})
    assert resolve_target_permission(policy, "device", "target-1", POLICY_READ) is True
    assert resolve_target_permission(policy, "area", "target-1", POLICY_EDIT) is True
    assert (
        resolve_target_permission(policy, "domain", "light", POLICY_CONFIGURE) is True
    )


def test_resolve_target_empty_policy_denies() -> None:
    """Test an empty policy denies every target."""
    policy = POLICY_SCHEMA({})
    assert (
        resolve_target_permission(policy, "device", "target-1", POLICY_READ) is False
    )
    assert (
        resolve_target_permission(policy, "area", "target-1", POLICY_CONTROL) is False
    )
    assert (
        resolve_target_permission(policy, "domain", "light", POLICY_EDIT) is False
    )


def test_policy_permissions_target_checks_share_one_resolver() -> None:
    """Test device, area, and domain checks resolve through one shared path."""
    policy = POLICY_SCHEMA(
        {
            "entities": {
                "device_ids": {"device-1": {"read": True}},
                "area_ids": {"area-1": {"control": True}},
                "domains": {"light": {"configure": True}},
            }
        }
    )
    permissions = PolicyPermissions(policy, None)
    assert permissions.check_device("device-1", POLICY_READ) is True
    assert permissions.check_device("device-1", POLICY_CONTROL) is False
    assert permissions.check_area("area-1", POLICY_CONTROL) is True
    assert permissions.check_area("area-1", POLICY_READ) is False
    assert permissions.check_domain("light", POLICY_CONFIGURE) is True
    assert permissions.check_domain("switch", POLICY_CONFIGURE) is False


def test_owner_target_checks_allow_all() -> None:
    """Test the owner keeps full access to every target."""
    assert OwnerPermissions.check_device("device-1", POLICY_READ) is True
    assert OwnerPermissions.check_area("area-1", POLICY_EDIT) is True
    assert OwnerPermissions.check_domain("light", POLICY_CONFIGURE) is True
