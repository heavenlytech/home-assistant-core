"""Offer API to configure Home Assistant auth."""

from typing import Any

import probatio

from homeassistant.auth.models import Group, User
from homeassistant.auth.permissions import POLICY_SCHEMA
from homeassistant.auth.permissions.system_policies import ACCESS_MODES
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback


@callback
def async_setup(hass: HomeAssistant) -> bool:
    """Enable the Home Assistant views."""
    websocket_api.async_register_command(hass, websocket_list)
    websocket_api.async_register_command(hass, websocket_delete)
    websocket_api.async_register_command(hass, websocket_create)
    websocket_api.async_register_command(hass, websocket_update)
    websocket_api.async_register_command(hass, websocket_permissions_get)
    websocket_api.async_register_command(hass, websocket_permissions_update)
    websocket_api.async_register_command(hass, websocket_defaults_get)
    websocket_api.async_register_command(hass, websocket_defaults_update)
    websocket_api.async_register_command(hass, websocket_group_list)
    websocket_api.async_register_command(hass, websocket_group_create)
    websocket_api.async_register_command(hass, websocket_group_update)
    websocket_api.async_register_command(hass, websocket_group_delete)
    return True


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "config/auth/list"})
@websocket_api.async_response
async def websocket_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return a list of users."""
    result = [_user_info(u) for u in await hass.auth.async_get_users()]

    connection.send_message(websocket_api.result_message(msg["id"], result))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {probatio.Required("type"): "config/auth/delete", probatio.Required("user_id"): str}
)
@websocket_api.async_response
async def websocket_delete(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Delete a user."""
    if msg["user_id"] == connection.user.id:
        connection.send_message(
            websocket_api.error_message(
                msg["id"], "no_delete_self", "Unable to delete your own account"
            )
        )
        return

    if not (user := await hass.auth.async_get_user(msg["user_id"])):
        connection.send_message(
            websocket_api.error_message(msg["id"], "not_found", "User not found")
        )
        return

    if user.system_generated:
        connection.send_message(
            websocket_api.error_message(
                msg["id"],
                "cannot_modify_system_generated",
                "Unable to delete system generated users.",
            )
        )
        return

    if user.is_owner:
        connection.send_message(
            websocket_api.error_message(
                msg["id"], "cannot_delete_owner", "Unable to delete the owner"
            )
        )
        return

    await hass.auth.async_remove_user(user)

    connection.send_message(websocket_api.result_message(msg["id"]))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "config/auth/create",
        probatio.Required("name"): str,
        probatio.Optional("group_ids"): [str],
        probatio.Optional("local_only"): bool,
    }
)
@websocket_api.async_response
async def websocket_create(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create a user."""
    user = await hass.auth.async_create_user(
        msg["name"], group_ids=msg.get("group_ids"), local_only=msg.get("local_only")
    )

    connection.send_message(
        websocket_api.result_message(msg["id"], {"user": _user_info(user)})
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "config/auth/update",
        probatio.Required("user_id"): str,
        probatio.Optional("name"): str,
        probatio.Optional("is_active"): bool,
        probatio.Optional("group_ids"): [str],
        probatio.Optional("local_only"): bool,
    }
)
@websocket_api.async_response
async def websocket_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update a user."""
    if not (user := await hass.auth.async_get_user(msg.pop("user_id"))):
        connection.send_message(
            websocket_api.error_message(
                msg["id"], websocket_api.ERR_NOT_FOUND, "User not found"
            )
        )
        return

    if user.system_generated:
        connection.send_message(
            websocket_api.error_message(
                msg["id"],
                "cannot_modify_system_generated",
                "Unable to update system generated users.",
            )
        )
        return

    if user.is_owner and msg.get("is_active") is False:
        connection.send_message(
            websocket_api.error_message(
                msg["id"],
                "cannot_deactivate_owner",
                "Unable to deactivate owner.",
            )
        )
        return

    msg.pop("type")
    msg_id = msg.pop("id")

    await hass.auth.async_update_user(user, **msg)

    connection.send_message(
        websocket_api.result_message(msg_id, {"user": _user_info(user)})
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "config/auth/permissions/get",
        probatio.Required("user_id"): str,
    }
)
@websocket_api.async_response
async def websocket_permissions_get(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the granular permission rules of a user."""
    if not (user := await hass.auth.async_get_user(msg["user_id"])):
        connection.send_message(
            websocket_api.error_message(
                msg["id"], websocket_api.ERR_NOT_FOUND, "User not found"
            )
        )
        return

    connection.send_message(
        websocket_api.result_message(msg["id"], {"policy": user.policy or {}})
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "config/auth/permissions/update",
        probatio.Required("user_id"): str,
        probatio.Required("policy"): probatio.Any(None, POLICY_SCHEMA),
    }
)
@websocket_api.async_response
async def websocket_permissions_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Set or clear the granular permission rules of a user.

    A policy of None clears every direct rule of the user.
    """
    if not (user := await hass.auth.async_get_user(msg["user_id"])):
        connection.send_message(
            websocket_api.error_message(
                msg["id"], websocket_api.ERR_NOT_FOUND, "User not found"
            )
        )
        return

    if user.system_generated:
        connection.send_message(
            websocket_api.error_message(
                msg["id"],
                "cannot_modify_system_generated",
                "Unable to update system generated users.",
            )
        )
        return

    if user.is_owner:
        connection.send_message(
            websocket_api.error_message(
                msg["id"],
                "cannot_modify_owner_permissions",
                "The owner always has full access.",
            )
        )
        return

    await hass.auth.async_update_user_policy(user, msg["policy"])

    connection.send_message(
        websocket_api.result_message(msg["id"], {"policy": user.policy or {}})
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {probatio.Required("type"): "config/auth/defaults/get"}
)
@websocket_api.async_response
async def websocket_defaults_get(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the default access mode for ordinary users."""
    connection.send_message(
        websocket_api.result_message(
            msg["id"], {"mode": await hass.auth.async_get_access_mode()}
        )
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "config/auth/defaults/update",
        probatio.Required("mode"): probatio.In(ACCESS_MODES),
    }
)
@websocket_api.async_response
async def websocket_defaults_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Set the default access mode for ordinary users."""
    await hass.auth.async_update_access_mode(msg["mode"])

    connection.send_message(
        websocket_api.result_message(
            msg["id"], {"mode": await hass.auth.async_get_access_mode()}
        )
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {probatio.Required("type"): "config/auth/group/list"}
)
@websocket_api.async_response
async def websocket_group_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return every group with its rules and member identifiers."""
    users = await hass.auth.async_get_users()
    members: dict[str, list[str]] = {}
    for user in users:
        for group in user.groups:
            members.setdefault(group.id, []).append(user.id)
    result = [
        _group_info(group, members.get(group.id, []))
        for group in await hass.auth.async_get_groups()
    ]
    connection.send_message(websocket_api.result_message(msg["id"], result))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "config/auth/group/create",
        probatio.Required("name"): str,
        probatio.Optional("policy"): POLICY_SCHEMA,
    }
)
@websocket_api.async_response
async def websocket_group_create(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create a custom group with the same rule shape as user rules."""
    try:
        group = await hass.auth.async_create_group(
            msg["name"], msg.get("policy")
        )
    except ValueError as err:
        connection.send_message(
            websocket_api.error_message(msg["id"], "invalid_name", str(err))
        )
        return
    connection.send_message(
        websocket_api.result_message(msg["id"], {"group": _group_info(group, [])})
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "config/auth/group/update",
        probatio.Required("group_id"): str,
        probatio.Optional("name"): str,
        probatio.Optional("policy"): POLICY_SCHEMA,
    }
)
@websocket_api.async_response
async def websocket_group_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update the name or rules of a custom group."""
    if not (group := await hass.auth.async_get_group(msg["group_id"])):
        connection.send_message(
            websocket_api.error_message(
                msg["id"], websocket_api.ERR_NOT_FOUND, "Group not found"
            )
        )
        return
    if group.system_generated:
        connection.send_message(
            websocket_api.error_message(
                msg["id"],
                "cannot_modify_system_group",
                "System groups cannot be modified.",
            )
        )
        return
    try:
        await hass.auth.async_update_group(
            group, msg.get("name"), msg.get("policy")
        )
    except ValueError as err:
        connection.send_message(
            websocket_api.error_message(msg["id"], "invalid_name", str(err))
        )
        return
    users = await hass.auth.async_get_users()
    member_ids = [
        user.id for user in users if any(g.id == group.id for g in user.groups)
    ]
    connection.send_message(
        websocket_api.result_message(
            msg["id"], {"group": _group_info(group, member_ids)}
        )
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "config/auth/group/delete",
        probatio.Required("group_id"): str,
    }
)
@websocket_api.async_response
async def websocket_group_delete(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Delete a custom group and remove it from every member."""
    if not (group := await hass.auth.async_get_group(msg["group_id"])):
        connection.send_message(
            websocket_api.error_message(
                msg["id"], websocket_api.ERR_NOT_FOUND, "Group not found"
            )
        )
        return
    if group.system_generated:
        connection.send_message(
            websocket_api.error_message(
                msg["id"],
                "cannot_modify_system_group",
                "System groups cannot be deleted.",
            )
        )
        return
    await hass.auth.async_delete_group(group)
    connection.send_message(websocket_api.result_message(msg["id"]))


def _group_info(group: Group, member_ids: list[str]) -> dict[str, Any]:
    """Format a group with its rules and member identifiers."""
    return {
        "id": group.id,
        "name": group.name,
        "system_generated": group.system_generated,
        "policy": group.policy,
        "member_ids": member_ids,
    }


def _user_info(user: User) -> dict[str, Any]:
    """Format a user."""

    ha_username = next(
        (
            cred.data.get("username")
            for cred in user.credentials
            if cred.auth_provider_type == "homeassistant"
        ),
        None,
    )

    return {
        "id": user.id,
        "username": ha_username,
        "name": user.name,
        "is_owner": user.is_owner,
        "is_active": user.is_active,
        "local_only": user.local_only,
        "system_generated": user.system_generated,
        "group_ids": [group.id for group in user.groups],
        "credentials": [{"type": c.auth_provider_type} for c in user.credentials],
    }
