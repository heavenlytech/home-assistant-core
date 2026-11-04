"""Permissions for Home Assistant."""

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, override

import probatio

from .const import CAT_ENTITIES, SUBCAT_ALL
from .entities import (
    ENTITY_AREAS,
    ENTITY_DEVICE_IDS,
    ENTITY_DOMAINS,
    ENTITY_POLICY_SCHEMA,
    compile_entities,
    device_area_ids,
)
from .merge import merge_policies
from .models import PermissionLookup
from .types import PolicyType, ValueType
from .util import test_all

if TYPE_CHECKING:
    from ..models import User

POLICY_SCHEMA = probatio.Schema({probatio.Optional(CAT_ENTITIES): ENTITY_POLICY_SCHEMA})

TARGET_DEVICE = "device"
TARGET_AREA = "area"
TARGET_DOMAIN = "domain"

_TARGET_SUBCATEGORY = {
    TARGET_DEVICE: ENTITY_DEVICE_IDS,
    TARGET_AREA: ENTITY_AREAS,
    TARGET_DOMAIN: ENTITY_DOMAINS,
}

__all__ = [
    "POLICY_SCHEMA",
    "TARGET_AREA",
    "TARGET_DEVICE",
    "TARGET_DOMAIN",
    "AbstractPermissions",
    "OwnerPermissions",
    "PermissionLookup",
    "PolicyPermissions",
    "PolicyType",
    "filter_entity_ids_by_permission",
    "merge_policies",
    "resolve_target_permission",
]


def filter_entity_ids_by_permission(
    user: User, entity_ids: Iterable[str], key: str
) -> list[str]:
    """Filter entity IDs to those the user can access for the given policy key."""
    if user.is_admin or user.permissions.access_all_entities(key):
        return list(entity_ids)
    check_entity = user.permissions.check_entity
    return [entity_id for entity_id in entity_ids if check_entity(entity_id, key)]


def _test_rule(rule: ValueType, key: str) -> bool | None:
    """Test a single policy rule for a key.

    Returns True when allowed, False when explicitly denied, and None when
    the rule holds no opinion so the caller can fall through to the next rule.
    """
    if rule is True:
        return True
    if isinstance(rule, dict):
        result = rule.get(key)
        return result if result is None else bool(result)
    if rule is False:
        return False
    return None


def resolve_target_permission(
    policy: PolicyType,
    target_type: str,
    target_id: str,
    key: str,
    perm_lookup: PermissionLookup | None = None,
) -> bool:
    """Resolve permission for one device, area, or domain target.

    This is the single shared resolver reused by every non-entity target:
    the direct rule for the target wins, then the areas holding a device,
    and the all rule is the fallback. An explicit denial stops the lookup;
    a missing rule falls through.
    """
    category = policy.get(CAT_ENTITIES)
    if category is True:
        return True
    if not isinstance(category, dict):
        return False
    subcategory = category.get(_TARGET_SUBCATEGORY[target_type])
    if isinstance(subcategory, bool):
        return subcategory
    if isinstance(subcategory, dict):
        if (result := _test_rule(subcategory.get(target_id), key)) is not None:
            return result
    if target_type == TARGET_DEVICE:
        area_rules = category.get(ENTITY_AREAS)
        if area_rules is True:
            return True
        if isinstance(area_rules, dict):
            for area_id in device_area_ids(perm_lookup, target_id):
                if _test_rule(area_rules.get(area_id), key) is True:
                    return True
    return _test_rule(category.get(SUBCAT_ALL), key) is True


class AbstractPermissions:
    """Default permissions class."""

    _cached_entity_func: Callable[[str, str], bool] | None = None

    def _entity_func(self) -> Callable[[str, str], bool]:
        """Return a function that can test entity access."""
        raise NotImplementedError

    def access_all_entities(self, key: str) -> bool:
        """Check if we have a certain access to all entities."""
        raise NotImplementedError

    def check_entity(self, entity_id: str, key: str) -> bool:
        """Check if we can access entity."""
        if (entity_func := self._cached_entity_func) is None:
            entity_func = self._cached_entity_func = self._entity_func()

        return entity_func(entity_id, key)

    def check_device(self, device_id: str, key: str) -> bool:
        """Check if we can access a device."""
        raise NotImplementedError

    def check_area(self, area_id: str, key: str) -> bool:
        """Check if we can access an area."""
        raise NotImplementedError

    def check_domain(self, domain: str, key: str) -> bool:
        """Check if we can access a domain."""
        raise NotImplementedError


class PolicyPermissions(AbstractPermissions):
    """Handle permissions."""

    def __init__(self, policy: PolicyType, perm_lookup: PermissionLookup) -> None:
        """Initialize the permission class."""
        self._policy = policy
        self._perm_lookup = perm_lookup

    @override
    def access_all_entities(self, key: str) -> bool:
        """Check if we have a certain access to all entities."""
        return test_all(self._policy.get(CAT_ENTITIES), key)

    @override
    def _entity_func(self) -> Callable[[str, str], bool]:
        """Return a function that can test entity access."""
        return compile_entities(self._policy.get(CAT_ENTITIES), self._perm_lookup)

    @override
    def check_device(self, device_id: str, key: str) -> bool:
        """Check if we can access a device."""
        return resolve_target_permission(
            self._policy, TARGET_DEVICE, device_id, key, self._perm_lookup
        )

    @override
    def check_area(self, area_id: str, key: str) -> bool:
        """Check if we can access an area."""
        return resolve_target_permission(self._policy, TARGET_AREA, area_id, key)

    @override
    def check_domain(self, domain: str, key: str) -> bool:
        """Check if we can access a domain."""
        return resolve_target_permission(self._policy, TARGET_DOMAIN, domain, key)

    @override
    def __eq__(self, other: object) -> bool:
        """Equals check."""
        return isinstance(other, PolicyPermissions) and other._policy == self._policy


class _OwnerPermissions(AbstractPermissions):
    """Owner permissions."""

    @override
    def access_all_entities(self, key: str) -> bool:
        """Check if we have a certain access to all entities."""
        return True

    @override
    def _entity_func(self) -> Callable[[str, str], bool]:
        """Return a function that can test entity access."""
        return lambda entity_id, key: True

    @override
    def check_device(self, device_id: str, key: str) -> bool:
        """Check if we can access a device."""
        return True

    @override
    def check_area(self, area_id: str, key: str) -> bool:
        """Check if we can access an area."""
        return True

    @override
    def check_domain(self, domain: str, key: str) -> bool:
        """Check if we can access a domain."""
        return True


OwnerPermissions = _OwnerPermissions()
