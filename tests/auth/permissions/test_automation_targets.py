"""Tests for the automate right and automation target enforcement."""

from homeassistant.auth import models, permissions
from homeassistant.auth.permissions.automation_targets import (
    check_automation_targets,
    extract_automation_targets,
)
from homeassistant.auth.permissions.const import POLICY_AUTOMATE, POLICY_READ


def test_extract_targets_from_nested_config() -> None:
    """Test device, entity, and area names are found at any depth."""
    config = {
        "trigger": [{"platform": "device", "device_id": "device-1"}],
        "condition": [{"condition": "state", "entity_id": ["light.a", "light.b"]}],
        "action": [
            {"service": "light.turn_on", "target": {"area_id": "area-1"}},
            {"service": "light.turn_on", "target": {"floor_id": "floor-1"}},
            {"device_id": "device-2"},
        ],
    }
    devices, entities, areas, floors = extract_automation_targets(config)
    assert devices == {"device-1", "device-2"}
    assert entities == {"light.a", "light.b"}
    assert areas == {"area-1"}
    assert floors == {"floor-1"}


def test_extract_targets_from_scene_entities() -> None:
    """Test scene entity maps contribute their keys as entities."""
    config = {"entities": {"light.kitchen": {"state": "on"}}}
    devices, entities, areas, floors = extract_automation_targets(config)
    assert entities == {"light.kitchen"}
    assert devices == set()
    assert areas == set()
    assert floors == set()


def test_automate_right_resolves_per_target() -> None:
    """Test the automate right grants each target separately."""
    policy = permissions.POLICY_SCHEMA(
        {"entities": {"device_ids": {"device-1": {"automate": True}}}}
    )
    assert (
        permissions.resolve_target_permission(
            policy, "device", "device-1", POLICY_AUTOMATE
        )
        is True
    )
    assert (
        permissions.resolve_target_permission(
            policy, "device", "device-1", POLICY_READ
        )
        is False
    )
    assert (
        permissions.resolve_target_permission(
            policy, "device", "device-2", POLICY_AUTOMATE
        )
        is False
    )


def test_check_automation_targets_requires_every_target() -> None:
    """Test every named target must grant automate."""
    group = models.Group(
        name="Test",
        policy={"entities": {"device_ids": {"device-1": {"automate": True}}}},
    )
    user = models.User(name="Test", perm_lookup=None, groups=[group])
    assert (
        check_automation_targets(user.permissions, {"device-1"}, set(), set())
        is True
    )
    assert (
        check_automation_targets(
            user.permissions, {"device-1", "device-2"}, set(), set()
        )
        is False
    )


def test_check_automation_targets_requires_named_floors() -> None:
    """Test a named floor without an automate grant blocks the entry."""
    group = models.Group(
        name="Test",
        policy={"entities": {"floor_ids": {"floor-1": {"automate": True}}}},
    )
    user = models.User(name="Test", perm_lookup=None, groups=[group])
    assert (
        check_automation_targets(
            user.permissions, set(), set(), set(), {"floor-1"}
        )
        is True
    )
    assert (
        check_automation_targets(
            user.permissions, set(), set(), set(), {"floor-2"}
        )
        is False
    )


def test_check_automation_targets_empty_requires_all() -> None:
    """Test an empty target set requires the all automate grant."""
    group = models.Group(
        name="Test",
        policy={"entities": {"device_ids": {"device-1": {"automate": True}}}},
    )
    user = models.User(name="Test", perm_lookup=None, groups=[group])
    assert check_automation_targets(user.permissions, set(), set(), set()) is False

    open_group = models.Group(name="Open", policy={"entities": True})
    open_user = models.User(name="Open", perm_lookup=None, groups=[open_group])
    assert check_automation_targets(open_user.permissions, set(), set(), set()) is True
