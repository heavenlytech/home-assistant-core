"""Tests for custom groups and the integration access rule helpers."""

import pytest

from homeassistant.auth import (
    EVENT_ACCESS_MODE_UPDATED,
    EVENT_GROUP_ADDED,
    EVENT_GROUP_REMOVED,
    EVENT_GROUP_UPDATED,
    EVENT_USER_UPDATED,
)
from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_USER
from homeassistant.auth.permissions.access_rules import (
    async_check_target,
    async_get_group_rules,
    async_get_user_rules,
    async_set_group_rules,
    async_set_user_rules,
    async_subscribe_rule_changes,
)
from homeassistant.core import HomeAssistant


async def test_create_group_with_rules(hass: HomeAssistant) -> None:
    """Test creating a custom group stores the same rule shape as users."""
    policy = {"entities": {"device_ids": {"device-1": {"read": True}}}}
    group = await hass.auth.async_create_group("Family", policy)
    assert group.name == "Family"
    assert group.policy == policy
    assert group.system_generated is False

    reloaded = await hass.auth.async_get_group(group.id)
    assert reloaded is group


async def test_create_group_requires_name(hass: HomeAssistant) -> None:
    """Test creating a group without a name fails."""
    with pytest.raises(ValueError, match="must not be empty"):
        await hass.auth.async_create_group("   ")


async def test_update_group_policy_merges_with_user(hass: HomeAssistant) -> None:
    """Test group grants merge with direct user rules, most permissive wins."""
    await hass.auth.async_create_user("Owner")
    group = await hass.auth.async_create_group(
        "Family", {"entities": {"device_ids": {"device-1": {"read": True}}}}
    )
    user = await hass.auth.async_create_user("Member", group_ids=[group.id])
    assert user.permissions.check_device("device-1", "read") is True
    assert user.permissions.check_device("device-1", "control") is False

    await hass.auth.async_update_group(
        group, policy={"entities": {"device_ids": {"device-1": {"control": True}}}}
    )
    assert user.permissions.check_device("device-1", "read") is False
    assert user.permissions.check_device("device-1", "control") is True

    await hass.auth.async_update_user_policy(
        user, {"entities": {"device_ids": {"device-1": {"read": True}}}}
    )
    assert user.permissions.check_device("device-1", "read") is True
    assert user.permissions.check_device("device-1", "control") is True


async def test_delete_group_removes_from_members(hass: HomeAssistant) -> None:
    """Test deleting a group removes it from every member."""
    await hass.auth.async_create_user("Owner")
    group = await hass.auth.async_create_group("Temporary", {})
    user = await hass.auth.async_create_user("Member", group_ids=[group.id])
    assert [g.id for g in user.groups] == [group.id]

    await hass.auth.async_delete_group(group)
    assert await hass.auth.async_get_group(group.id) is None
    assert user.groups == []


async def test_system_groups_protected(hass: HomeAssistant) -> None:
    """Test system groups cannot be updated or deleted."""
    admin_group = await hass.auth.async_get_group(GROUP_ID_ADMIN)
    assert admin_group is not None
    with pytest.raises(ValueError, match="cannot be modified"):
        await hass.auth.async_update_group(admin_group, name="Changed")
    with pytest.raises(ValueError, match="cannot be deleted"):
        await hass.auth.async_delete_group(admin_group)


async def test_open_unless_specified_limits_custom_group_members(
    hass: HomeAssistant,
) -> None:
    """Test custom group members are limited to explicit grants alone."""
    await hass.auth.async_create_user("Owner")
    await hass.auth.async_update_access_mode("open_unless_specified")
    group = await hass.auth.async_create_group(
        "Family", {"entities": {"device_ids": {"device-1": {"read": True}}}}
    )
    member = await hass.auth.async_create_user(
        "Member", group_ids=[GROUP_ID_USER, group.id]
    )
    plain = await hass.auth.async_create_user("Plain", group_ids=[GROUP_ID_USER])

    assert member.permissions.check_device("device-1", "read") is True
    assert member.permissions.check_device("device-2", "read") is False
    assert plain.permissions.check_device("device-2", "read") is True


async def test_administrator_keeps_full_access_with_direct_rules(
    hass: HomeAssistant,
) -> None:
    """Test administrators stay open even with direct rules set."""
    await hass.auth.async_create_user("Owner")
    await hass.auth.async_update_access_mode("open_unless_specified")
    admin = await hass.auth.async_create_user(
        "Admin", group_ids=[GROUP_ID_ADMIN]
    )
    await hass.auth.async_update_user_policy(
        admin, {"entities": {"device_ids": {"device-1": {"read": True}}}}
    )
    assert admin.is_admin is True
    assert admin.permissions.check_device("device-2", "read") is True


async def test_access_rules_helper_user_read_write(hass: HomeAssistant) -> None:
    """Test the integration helper reads and writes user rules."""
    await hass.auth.async_create_user("Owner")
    user = await hass.auth.async_create_user("Member")
    assert await async_get_user_rules(hass, user.id) is None
    assert await async_get_user_rules(hass, "unknown") is None

    policy = {"entities": {"area_ids": {"area-1": {"read": True}}}}
    assert await async_set_user_rules(hass, user.id, policy) == policy
    assert await async_get_user_rules(hass, user.id) == policy
    assert await async_check_target(hass, user.id, "area", "area-1", "read") is True
    assert await async_check_target(hass, "unknown", "area", "area-1", "read") is False

    assert await async_set_user_rules(hass, user.id, None) is None
    assert await async_get_user_rules(hass, user.id) is None


async def test_access_rules_helper_rejects_owner(hass: HomeAssistant) -> None:
    """Test the helper protects the owner from rule changes."""
    owner = await hass.auth.async_get_owner()
    if owner is None:
        owner = await hass.auth.async_create_user("Owner")
        owner.is_owner = True
    with pytest.raises(ValueError, match="full access"):
        await async_set_user_rules(hass, owner.id, {})


async def test_access_rules_helper_group_read_write(hass: HomeAssistant) -> None:
    """Test the helper reads and writes custom group rules."""
    group = await hass.auth.async_create_group("Family", {})
    assert await async_get_group_rules(hass, group.id) == {}
    assert await async_get_group_rules(hass, "unknown") is None

    policy = {"entities": {"domains": {"light": {"control": True}}}}
    assert await async_set_group_rules(hass, group.id, policy) == policy
    assert await async_get_group_rules(hass, group.id) == policy

    with pytest.raises(ValueError, match="System groups"):
        await async_set_group_rules(hass, GROUP_ID_USER, {})


async def test_access_rules_subscribe_reports_changes(hass: HomeAssistant) -> None:
    """Test integrations receive user, group, and mode change events."""
    await hass.auth.async_create_user("Owner")
    seen: list[str] = []
    async_subscribe_rule_changes(
        hass, lambda event_type, data: seen.append(event_type)
    )

    group = await hass.auth.async_create_group("Family", {})
    await hass.auth.async_update_group(group, name="Relatives")
    user = await hass.auth.async_create_user("Member", group_ids=[group.id])
    await hass.auth.async_update_user_policy(user, {"entities": {"all": {"read": True}}})
    await hass.auth.async_update_access_mode("read_only")
    await hass.auth.async_delete_group(group)
    await hass.async_block_till_done()

    assert EVENT_GROUP_ADDED in seen
    assert EVENT_GROUP_UPDATED in seen
    assert EVENT_GROUP_REMOVED in seen
    assert EVENT_USER_UPDATED in seen
    assert EVENT_ACCESS_MODE_UPDATED in seen


async def test_access_rules_helper_checks_floors(hass: HomeAssistant) -> None:
    """Test the integration helper checks the floor target type."""
    await hass.auth.async_create_user("Owner")
    user = await hass.auth.async_create_user("Member")
    policy = {"entities": {"floor_ids": {"floor-1": {"read": True}}}}
    await async_set_user_rules(hass, user.id, policy)
    assert await async_check_target(hass, user.id, "floor", "floor-1", "read") is True
    assert (
        await async_check_target(hass, user.id, "floor", "floor-2", "read") is False
    )
