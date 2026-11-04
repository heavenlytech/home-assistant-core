"""HTTP views to interact with the area registry."""

from typing import Any

import probatio

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.auth.permissions.upward import upward_area_ids
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar, label_registry as lr
from homeassistant.helpers.json import json_fragment


@callback
def async_setup(hass: HomeAssistant) -> bool:
    """Enable the Area Registry views."""
    websocket_api.async_register_command(hass, websocket_list_areas)
    websocket_api.async_register_command(hass, websocket_create_area)
    websocket_api.async_register_command(hass, websocket_delete_area)
    websocket_api.async_register_command(hass, websocket_update_area)
    websocket_api.async_register_command(hass, websocket_reorder_areas)
    return True


@websocket_api.websocket_command(
    {probatio.Required("type"): "config/area_registry/list"}
)
@callback
def websocket_list_areas(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle list areas command."""
    registry = ar.async_get(hass)
    user = connection.user
    if user.is_admin:
        payload: list[json_fragment | dict] = [
            entry.json_fragment for entry in registry.async_list_areas()
        ]
    else:
        check_area = user.permissions.check_area
        upward = upward_area_ids(hass, user)
        payload = []
        for entry in registry.async_list_areas():
            if check_area(entry.id, POLICY_READ):
                payload.append(entry.json_fragment)
            elif entry.id in upward:
                payload.append(
                    {
                        "aliases": [],
                        "area_id": entry.id,
                        "floor_id": entry.floor_id,
                        "humidity_entity_id": None,
                        "icon": None,
                        "labels": [],
                        "name": entry.name,
                        "picture": None,
                        "temperature_entity_id": None,
                        "created_at": entry.created_at.timestamp(),
                        "modified_at": entry.modified_at.timestamp(),
                    }
                )
    connection.send_result(msg["id"], payload)


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "config/area_registry/create",
        probatio.Optional("aliases"): list,
        probatio.Optional("floor_id"): str,
        probatio.Optional("humidity_entity_id"): probatio.Any(str, None),
        probatio.Optional("icon"): str,
        probatio.Optional("labels"): [str],
        probatio.Required("name"): str,
        probatio.Optional("picture"): probatio.Any(str, None),
        probatio.Optional("temperature_entity_id"): probatio.Any(str, None),
    }
)
@websocket_api.require_admin
@callback
def websocket_create_area(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create area command."""
    registry = ar.async_get(hass)

    data = dict(msg)
    data.pop("type")
    data.pop("id")

    if "aliases" in data:
        # Create a set for the aliases without:
        #   - Empty strings
        #   - Trailing and leading whitespace characters in the individual aliases
        data["aliases"] = {s_strip for s in data["aliases"] if (s_strip := s.strip())}

    if "labels" in data:
        labels = set(data["labels"])
        data["labels"] = labels - lr.async_get_missing_label_ids(hass, labels)

    try:
        entry = registry.async_create(**data)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_info", str(err))
    else:
        connection.send_result(msg["id"], entry.json_fragment)


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "config/area_registry/delete",
        probatio.Required("area_id"): str,
    }
)
@websocket_api.require_admin
@callback
def websocket_delete_area(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Delete area command."""
    registry = ar.async_get(hass)

    try:
        registry.async_delete(msg["area_id"])
    except KeyError:
        connection.send_error(msg["id"], "invalid_info", "Area ID doesn't exist")
    else:
        connection.send_message(websocket_api.result_message(msg["id"], "success"))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "config/area_registry/update",
        probatio.Optional("aliases"): list,
        probatio.Required("area_id"): str,
        probatio.Optional("floor_id"): probatio.Any(str, None),
        probatio.Optional("humidity_entity_id"): probatio.Any(str, None),
        probatio.Optional("icon"): probatio.Any(str, None),
        probatio.Optional("labels"): [str],
        probatio.Optional("name"): str,
        probatio.Optional("picture"): probatio.Any(str, None),
        probatio.Optional("temperature_entity_id"): probatio.Any(str, None),
    }
)
@websocket_api.require_configure_permission("area", "area_id")
@callback
def websocket_update_area(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle update area websocket command."""
    registry = ar.async_get(hass)

    data = dict(msg)
    data.pop("type")
    data.pop("id")

    if "aliases" in data:
        # Create a set for the aliases without:
        #   - Empty strings
        #   - Trailing and leading whitespace characters in the individual aliases
        data["aliases"] = {s_strip for s in data["aliases"] if (s_strip := s.strip())}

    if "labels" in data:
        labels = set(data["labels"])
        data["labels"] = labels - lr.async_get_missing_label_ids(hass, labels)

    try:
        entry = registry.async_update(**data)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_info", str(err))
    else:
        connection.send_result(msg["id"], entry.json_fragment)


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "config/area_registry/reorder",
        probatio.Required("area_ids"): [str],
    }
)
@websocket_api.require_admin
@callback
def websocket_reorder_areas(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle reorder areas websocket command."""
    registry = ar.async_get(hass)

    try:
        registry.async_reorder(msg["area_ids"])
    except ValueError as err:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, str(err))
    else:
        connection.send_result(msg["id"])
