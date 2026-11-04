"""Helpers to enforce the automate right on automation-like configuration."""

from typing import Any

from homeassistant.auth.permissions import AbstractPermissions
from homeassistant.auth.permissions.const import POLICY_AUTOMATE

__all__ = [
    "check_automation_targets",
    "extract_automation_targets",
]

_DEVICE_KEYS = {"device_id", "device_ids"}
_ENTITY_KEYS = {"entity_id", "entity_ids"}
_AREA_KEYS = {"area_id", "area_ids"}
_FLOOR_KEYS = {"floor_id", "floor_ids"}


def extract_automation_targets(
    config: dict[str, Any] | list[Any],
) -> tuple[set[str], set[str], set[str], set[str]]:
    """Collect device, entity, area, and floor identifiers from a configuration.

    Walks triggers, conditions, and actions recursively, so every naming
    of a device, entity, area, or floor is found no matter where it sits.
    Scene entity maps contribute their keys as entity identifiers.
    """
    devices: set[str] = set()
    entities: set[str] = set()
    areas: set[str] = set()
    floors: set[str] = set()
    _walk(config, devices, entities, areas, floors)
    return devices, entities, areas, floors


def _walk(
    node: Any,
    devices: set[str],
    entities: set[str],
    areas: set[str],
    floors: set[str],
) -> None:
    """Recursively collect target identifiers from one node."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _DEVICE_KEYS:
                devices.update(_as_strings(value))
            elif key in _ENTITY_KEYS:
                entities.update(_as_strings(value))
            elif key in _AREA_KEYS:
                areas.update(_as_strings(value))
            elif key in _FLOOR_KEYS:
                floors.update(_as_strings(value))
            elif key == "entities" and isinstance(value, dict):
                entities.update(str(item) for item in value if isinstance(item, str))
            else:
                _walk(value, devices, entities, areas, floors)
    elif isinstance(node, list):
        for item in node:
            _walk(item, devices, entities, areas, floors)


def _as_strings(value: Any) -> set[str]:
    """Normalize one identifier field to a set of strings."""
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {item for item in value if isinstance(item, str)}
    return set()


def check_automation_targets(
    permissions: AbstractPermissions,
    devices: set[str],
    entities: set[str],
    areas: set[str],
    floors: set[str] | None = None,
    right: str = POLICY_AUTOMATE,
) -> bool:
    """Return True when every named target grants the given right.

    An empty target set requires the all grant, so restricted users
    cannot create automations that name nothing to bypass the check.
    """
    floors = floors or set()
    if not devices and not entities and not areas and not floors:
        return permissions.access_all_entities(right)
    return (
        all(permissions.check_device(device_id, right) for device_id in devices)
        and all(
            permissions.check_entity(entity_id, right) for entity_id in entities
        )
        and all(permissions.check_area(area_id, right) for area_id in areas)
        and all(permissions.check_floor(floor_id, right) for floor_id in floors)
    )
