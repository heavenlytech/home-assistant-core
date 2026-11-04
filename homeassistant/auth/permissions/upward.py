"""Helpers for upward visibility of parent areas and floors.

When a restricted user can read a device, the area holding that device
appears by name so the hierarchy stays navigable, even without an
explicit area grant. Floors appear when they hold at least one such
area. Upward-only parents carry redacted fields; explicit grants keep
the full entry.
"""

from itertools import chain
from typing import TYPE_CHECKING

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.helpers import area_registry as ar, device_registry as dr

if TYPE_CHECKING:
    from homeassistant.auth.models import User
    from homeassistant.core import HomeAssistant

__all__ = [
    "upward_area_ids",
    "visible_area_ids",
]


def upward_area_ids(hass: HomeAssistant, user: User) -> set[str]:
    """Return areas that hold at least one readable device."""
    device_registry = dr.async_get(hass)
    check_device = user.permissions.check_device
    areas: set[str] = set()
    for entry in chain(device_registry.devices, device_registry.child_devices):
        if not check_device(entry.id, POLICY_READ):
            continue
        area_id = dr.async_get_effective_area_id(device_registry.hass, entry)
        if area_id is not None:
            areas.add(area_id)
    return areas


def visible_area_ids(hass: HomeAssistant, user: User) -> set[str]:
    """Return explicitly readable areas plus upward-visible areas."""
    check_area = user.permissions.check_area
    visible = {
        entry.id
        for entry in ar.async_get(hass).async_list_areas()
        if check_area(entry.id, POLICY_READ)
    }
    visible.update(upward_area_ids(hass, user))
    return visible
