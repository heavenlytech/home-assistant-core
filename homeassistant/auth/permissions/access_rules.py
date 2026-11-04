"""Shared access rule helpers for integrations.

This module is the documented entry point for integrations that need to
read, change, or track granular access rules. Rules use the same shape
for users and for custom groups: a policy with device, area, domain,
and entity grants under the entities category.

Integrations run with full privileges, so these helpers do not check a
calling user. They still protect the owner and system records from
accidental change, matching the administrator screens.
"""

from collections.abc import Callable
from typing import Any

from homeassistant.auth import (
    EVENT_ACCESS_MODE_UPDATED,
    EVENT_GROUP_ADDED,
    EVENT_GROUP_REMOVED,
    EVENT_GROUP_UPDATED,
    EVENT_USER_ADDED,
    EVENT_USER_REMOVED,
    EVENT_USER_UPDATED,
)
from homeassistant.auth.models import Group
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

from . import POLICY_SCHEMA, TARGET_AREA, TARGET_DEVICE, TARGET_DOMAIN, TARGET_FLOOR
from .const import (
    POLICY_AUTOMATE,
    POLICY_CONFIGURE,
    POLICY_CONTROL,
    POLICY_EDIT,
    POLICY_READ,
)
from .types import PolicyType

__all__ = [
    "POLICY_AUTOMATE",
    "POLICY_CONFIGURE",
    "POLICY_CONTROL",
    "POLICY_EDIT",
    "POLICY_READ",
    "TARGET_AREA",
    "TARGET_DEVICE",
    "TARGET_DOMAIN",
    "TARGET_FLOOR",
    "async_check_target",
    "async_get_group_rules",
    "async_get_user_rules",
    "async_list_groups",
    "async_set_group_rules",
    "async_set_user_rules",
    "async_subscribe_rule_changes",
]


async def async_get_user_rules(
    hass: HomeAssistant, user_id: str
) -> PolicyType | None:
    """Return the direct rules of a user, or None when unknown."""
    user = await hass.auth.async_get_user(user_id)
    if user is None:
        return None
    return user.policy


async def async_set_user_rules(
    hass: HomeAssistant, user_id: str, policy: PolicyType | None
) -> PolicyType | None:
    """Set or clear the direct rules of a user.

    A policy of None clears every direct rule. Raises ValueError for
    unknown users, the owner, or system generated users.
    """
    user = await hass.auth.async_get_user(user_id)
    if user is None:
        raise ValueError(f"Unknown user {user_id}")
    if user.is_owner:
        raise ValueError("The owner always has full access")
    if user.system_generated:
        raise ValueError("System generated users take no direct rules")
    validated = None if policy is None else POLICY_SCHEMA(policy)
    await hass.auth.async_update_user_policy(user, validated)
    return user.policy


async def async_list_groups(hass: HomeAssistant) -> list[Group]:
    """Return every group, including system groups."""
    return await hass.auth.async_get_groups()


async def async_get_group_rules(
    hass: HomeAssistant, group_id: str
) -> PolicyType | None:
    """Return the rules of a group, or None when unknown."""
    group = await hass.auth.async_get_group(group_id)
    if group is None:
        return None
    return group.policy


async def async_set_group_rules(
    hass: HomeAssistant, group_id: str, policy: PolicyType
) -> PolicyType:
    """Set the rules of a custom group.

    Raises ValueError for unknown groups or system groups.
    """
    group = await hass.auth.async_get_group(group_id)
    if group is None:
        raise ValueError(f"Unknown group {group_id}")
    if group.system_generated:
        raise ValueError("System groups cannot be modified")
    validated = POLICY_SCHEMA(policy)
    await hass.auth.async_update_group(group, policy=validated)
    return group.policy


async def async_check_target(
    hass: HomeAssistant,
    user_id: str,
    target_type: str,
    target_id: str,
    right: str,
) -> bool:
    """Check one right for a user on a device, area, domain, or floor target.

    Returns False for unknown users. Target type is one of device,
    area, domain, or floor. Right is one of read, control, edit, configure,
    or automate.
    """
    user = await hass.auth.async_get_user(user_id)
    if user is None:
        return False
    if target_type == TARGET_DEVICE:
        return user.permissions.check_device(target_id, right)
    if target_type == TARGET_AREA:
        return user.permissions.check_area(target_id, right)
    if target_type == TARGET_DOMAIN:
        return user.permissions.check_domain(target_id, right)
    if target_type == TARGET_FLOOR:
        return user.permissions.check_floor(target_id, right)
    raise ValueError(f"Unknown target type {target_type}")


@callback
def async_subscribe_rule_changes(
    hass: HomeAssistant,
    listener: Callable[[str, dict[str, Any]], None],
) -> CALLBACK_TYPE:
    """Track every access rule change.

    The listener receives the event type and event data for user
    changes, group changes, and default access mode changes. Returns
    a function that removes all subscriptions.
    """
    removers = [
        hass.bus.async_listen(
            event_type, lambda event: listener(event.event_type, event.data)
        )
        for event_type in (
            EVENT_USER_ADDED,
            EVENT_USER_UPDATED,
            EVENT_USER_REMOVED,
            EVENT_GROUP_ADDED,
            EVENT_GROUP_UPDATED,
            EVENT_GROUP_REMOVED,
            EVENT_ACCESS_MODE_UPDATED,
        )
    ]

    @callback
    def async_remove_all() -> None:
        for remove in removers:
            remove()

    return async_remove_all
