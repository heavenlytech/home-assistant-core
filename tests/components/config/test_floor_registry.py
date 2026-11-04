"""Test floor registry API."""

from datetime import datetime
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import CLIENT_ID, MockConfigEntry, MockUser
from pytest_homeassistant.typing import MockHAClientWebSocket, WebSocketGenerator
from pytest_unordered import unordered

from homeassistant.components.config import DOMAIN, floor_registry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    floor_registry as fr,
)
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow


@pytest.fixture(name="client")
async def client_fixture(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> MockHAClientWebSocket:
    """Fixture that can interact with the config manager API."""
    floor_registry.async_setup(hass)
    return await hass_ws_client(hass)


async def test_list_floors(
    client: MockHAClientWebSocket,
    floor_registry: fr.FloorRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test list entries."""
    created_1 = datetime.fromisoformat("2024-07-16T13:30:00.900075+00:00")
    freezer.move_to(created_1)
    floor_registry.async_create("First floor")

    created_2 = datetime.fromisoformat("2024-07-16T13:45:00.900075+00:00")
    freezer.move_to(created_2)
    floor_registry.async_create(
        name="Second floor",
        aliases={"top floor", "attic"},
        icon="mdi:home-floor-2",
        level=2,
    )

    assert len(floor_registry.floors) == 2

    # update first floor to change modified_at
    floor_registry.async_update(
        "first_floor",
        name="First floor...",
    )

    await client.send_json_auto_id({"type": "config/floor_registry/list"})

    msg = await client.receive_json()

    assert len(msg["result"]) == len(floor_registry.floors)
    assert msg["result"][0] == {
        "aliases": [],
        "created_at": created_1.timestamp(),
        "icon": None,
        "floor_id": "first_floor",
        "modified_at": created_2.timestamp(),
        "name": "First floor...",
        "level": None,
    }
    assert msg["result"][1] == {
        "aliases": unordered(["top floor", "attic"]),
        "created_at": created_2.timestamp(),
        "icon": "mdi:home-floor-2",
        "floor_id": "second_floor",
        "modified_at": created_2.timestamp(),
        "name": "Second floor",
        "level": 2,
    }


@pytest.mark.usefixtures("freezer")
async def test_create_floor(
    client: MockHAClientWebSocket,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test create entry."""
    await client.send_json_auto_id(
        {"type": "config/floor_registry/create", "name": "First floor"}
    )

    msg = await client.receive_json()

    assert len(floor_registry.floors) == 1
    assert msg["result"] == {
        "aliases": [],
        "created_at": utcnow().timestamp(),
        "icon": None,
        "floor_id": "first_floor",
        "modified_at": utcnow().timestamp(),
        "name": "First floor",
        "level": None,
    }

    await client.send_json_auto_id(
        {
            "name": "Second floor",
            "type": "config/floor_registry/create",
            "aliases": ["top floor", "attic"],
            "icon": "mdi:home-floor-2",
            "level": 2,
        }
    )

    msg = await client.receive_json()

    assert len(floor_registry.floors) == 2
    assert msg["result"] == {
        "aliases": unordered(["top floor", "attic"]),
        "created_at": utcnow().timestamp(),
        "icon": "mdi:home-floor-2",
        "floor_id": "second_floor",
        "modified_at": utcnow().timestamp(),
        "name": "Second floor",
        "level": 2,
    }

    # Floor with invalid aliases
    await client.send_json_auto_id(
        {
            "name": "Third floor",
            "type": "config/floor_registry/create",
            "aliases": ["", " "],
            "icon": "mdi:home-floor-2",
            "level": 3,
        }
    )

    msg = await client.receive_json()

    assert len(floor_registry.floors) == 3
    assert msg["result"] == {
        "aliases": [],
        "created_at": utcnow().timestamp(),
        "icon": "mdi:home-floor-2",
        "floor_id": "third_floor",
        "modified_at": utcnow().timestamp(),
        "name": "Third floor",
        "level": 3,
    }


async def test_create_floor_with_name_already_in_use(
    client: MockHAClientWebSocket,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test create entry that should fail."""
    floor_registry.async_create("First floor")
    assert len(floor_registry.floors) == 1

    await client.send_json_auto_id(
        {"name": "First floor", "type": "config/floor_registry/create"}
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert (
        msg["error"]["message"] == "The name First floor (firstfloor) is already in use"
    )
    assert len(floor_registry.floors) == 1


async def test_delete_floor(
    client: MockHAClientWebSocket,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test delete entry."""
    floor = floor_registry.async_create("First floor")
    assert len(floor_registry.floors) == 1

    await client.send_json_auto_id(
        {"floor_id": floor.floor_id, "type": "config/floor_registry/delete"}
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert not floor_registry.floors


async def test_delete_non_existing_floor(
    client: MockHAClientWebSocket,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test delete entry that should fail."""
    floor_registry.async_create("First floor")
    assert len(floor_registry.floors) == 1

    await client.send_json_auto_id(
        {
            "floor_id": "zaphotbeeblebrox",
            "type": "config/floor_registry/delete",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "Floor ID doesn't exist"
    assert len(floor_registry.floors) == 1


async def test_update_floor(
    client: MockHAClientWebSocket,
    floor_registry: fr.FloorRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update entry."""
    created_at = datetime.fromisoformat("2024-07-16T13:30:00.900075+00:00")
    freezer.move_to(created_at)
    floor = floor_registry.async_create("First floor")
    assert len(floor_registry.floors) == 1
    modified_at = datetime.fromisoformat("2024-07-16T13:45:00.900075+00:00")
    freezer.move_to(modified_at)

    await client.send_json_auto_id(
        {
            "floor_id": floor.floor_id,
            "name": "Second floor",
            "aliases": ["top floor", "attic"],
            "icon": "mdi:home-floor-2",
            "type": "config/floor_registry/update",
            "level": 2,
        }
    )

    msg = await client.receive_json()

    assert len(floor_registry.floors) == 1
    assert msg["result"] == {
        "aliases": unordered(["top floor", "attic"]),
        "created_at": created_at.timestamp(),
        "icon": "mdi:home-floor-2",
        "floor_id": floor.floor_id,
        "modified_at": modified_at.timestamp(),
        "name": "Second floor",
        "level": 2,
    }

    modified_at = datetime.fromisoformat("2024-07-16T13:50:00.900075+00:00")
    freezer.move_to(modified_at)
    await client.send_json_auto_id(
        {
            "floor_id": floor.floor_id,
            "name": "First floor",
            "aliases": [],
            "icon": None,
            "level": None,
            "type": "config/floor_registry/update",
        }
    )

    msg = await client.receive_json()

    assert len(floor_registry.floors) == 1
    assert msg["result"] == {
        "aliases": [],
        "created_at": created_at.timestamp(),
        "icon": None,
        "floor_id": floor.floor_id,
        "modified_at": modified_at.timestamp(),
        "name": "First floor",
        "level": None,
    }

    # Add invalid aliases
    modified_at = datetime.fromisoformat("2024-07-16T13:55:00.900075+00:00")
    freezer.move_to(modified_at)
    await client.send_json_auto_id(
        {
            "floor_id": floor.floor_id,
            "name": "First floor",
            "aliases": ["top floor", "attic", "", " "],
            "icon": None,
            "level": None,
            "type": "config/floor_registry/update",
        }
    )

    msg = await client.receive_json()

    assert len(floor_registry.floors) == 1
    assert msg["result"] == {
        "aliases": unordered(["top floor", "attic"]),
        "created_at": created_at.timestamp(),
        "icon": None,
        "floor_id": floor.floor_id,
        "modified_at": modified_at.timestamp(),
        "name": "First floor",
        "level": None,
    }

    # Add alias with trailing and leading whitespaces
    modified_at = datetime.fromisoformat("2024-07-16T13:55:00.900075+00:00")
    freezer.move_to(modified_at)
    await client.send_json_auto_id(
        {
            "floor_id": floor.floor_id,
            "name": "First floor",
            "aliases": ["top floor", "attic", "solaio "],
            "icon": None,
            "level": None,
            "type": "config/floor_registry/update",
        }
    )

    msg = await client.receive_json()

    assert len(floor_registry.floors) == 1
    assert msg["result"] == {
        "aliases": unordered(["top floor", "attic", "solaio"]),
        "created_at": created_at.timestamp(),
        "icon": None,
        "floor_id": floor.floor_id,
        "modified_at": modified_at.timestamp(),
        "name": "First floor",
        "level": None,
    }


async def test_update_with_name_already_in_use(
    client: MockHAClientWebSocket,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test update entry."""
    floor = floor_registry.async_create("First floor")
    floor_registry.async_create("Second floor")
    assert len(floor_registry.floors) == 2

    await client.send_json_auto_id(
        {
            "floor_id": floor.floor_id,
            "name": "Second floor",
            "type": "config/floor_registry/update",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert (
        msg["error"]["message"]
        == "The name Second floor (secondfloor) is already in use"
    )
    assert len(floor_registry.floors) == 2


async def test_reorder_floors(
    client: MockHAClientWebSocket, floor_registry: fr.FloorRegistry
) -> None:
    """Test reorder floors."""
    floor1 = floor_registry.async_create("First floor")
    floor2 = floor_registry.async_create("Second floor")
    floor3 = floor_registry.async_create("Third floor")

    await client.send_json_auto_id({"type": "config/floor_registry/list"})
    msg = await client.receive_json()
    assert [floor["floor_id"] for floor in msg["result"]] == [
        floor1.floor_id,
        floor2.floor_id,
        floor3.floor_id,
    ]

    await client.send_json_auto_id(
        {
            "type": "config/floor_registry/reorder",
            "floor_ids": [floor3.floor_id, floor1.floor_id, floor2.floor_id],
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    await client.send_json_auto_id({"type": "config/floor_registry/list"})
    msg = await client.receive_json()
    assert [floor["floor_id"] for floor in msg["result"]] == [
        floor3.floor_id,
        floor1.floor_id,
        floor2.floor_id,
    ]


async def test_reorder_floors_invalid_floor_ids(
    client: MockHAClientWebSocket, floor_registry: fr.FloorRegistry
) -> None:
    """Test reorder with invalid floor IDs."""
    floor1 = floor_registry.async_create("First floor")
    floor_registry.async_create("Second floor")

    await client.send_json_auto_id(
        {
            "type": "config/floor_registry/reorder",
            "floor_ids": [floor1.floor_id],
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"
    assert "must contain all existing floor IDs" in msg["error"]["message"]


async def test_reorder_floors_with_nonexistent_id(
    client: MockHAClientWebSocket, floor_registry: fr.FloorRegistry
) -> None:
    """Test reorder with nonexistent floor ID."""
    floor1 = floor_registry.async_create("First floor")
    floor2 = floor_registry.async_create("Second floor")

    await client.send_json_auto_id(
        {
            "type": "config/floor_registry/reorder",
            "floor_ids": [floor1.floor_id, floor2.floor_id, "nonexistent"],
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"


async def test_reorder_floors_persistence(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    floor_registry: fr.FloorRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test that floor reordering is persisted."""
    floor1 = floor_registry.async_create("First floor")
    floor2 = floor_registry.async_create("Second floor")
    floor3 = floor_registry.async_create("Third floor")

    await client.send_json_auto_id(
        {
            "type": "config/floor_registry/reorder",
            "floor_ids": [floor2.floor_id, floor3.floor_id, floor1.floor_id],
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    await hass.async_block_till_done()

    floor_ids = [floor.floor_id for floor in floor_registry.async_list_floors()]
    assert floor_ids == [floor2.floor_id, floor3.floor_id, floor1.floor_id]


async def test_list_floors_filtered_for_restricted_user(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    floor_registry: fr.FloorRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test floor list only shows floors holding readable areas."""
    assert await async_setup_component(hass, DOMAIN, {})
    shown = floor_registry.async_create("First floor")
    floor_registry.async_create("Second floor")
    area = area_registry.async_create("mock 1", floor_id=shown.floor_id)
    hidden_area = area_registry.async_create("mock 2")
    assert hidden_area.floor_id is None

    user = MockUser(is_active=True, groups=[]).add_to_hass(hass)
    user.policy = {"entities": {"area_ids": {area.id: {"read": True}}}}
    refresh_token = await hass.auth.async_create_refresh_token(user, CLIENT_ID)
    access_token = hass.auth.async_create_access_token(refresh_token)

    client = await hass_ws_client(hass, access_token)
    await client.send_json_auto_id({"type": "config/floor_registry/list"})
    msg = await client.receive_json()

    assert msg["success"], msg
    assert [floor["floor_id"] for floor in msg["result"]] == [shown.floor_id]


async def test_list_floors_upward_from_readable_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    floor_registry: fr.FloorRegistry,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test floors holding upward-visible areas appear with redacted fields."""
    assert await async_setup_component(hass, DOMAIN, {})
    shown = floor_registry.async_create("First floor", icon="mdi:home")
    floor_registry.async_create("Second floor")
    area = area_registry.async_create("Kitchen", floor_id=shown.floor_id)
    entry = MockConfigEntry()
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("test", "device-1")},
    )
    device_registry.async_update_device(device.id, area_id=area.id)

    user = MockUser(is_active=True, groups=[]).add_to_hass(hass)
    user.policy = {"entities": {"device_ids": {device.id: {"read": True}}}}
    refresh_token = await hass.auth.async_create_refresh_token(user, CLIENT_ID)
    access_token = hass.auth.async_create_access_token(refresh_token)

    client = await hass_ws_client(hass, access_token)
    await client.send_json_auto_id({"type": "config/floor_registry/list"})
    msg = await client.receive_json()

    assert msg["success"], msg
    assert [floor["floor_id"] for floor in msg["result"]] == [shown.floor_id]
    assert msg["result"][0]["name"] == "First floor"
    assert msg["result"][0]["icon"] is None


async def test_list_floors_direct_grant_shows_empty_floor_fully(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test a direct floor grant lists an empty floor with full fields."""
    assert await async_setup_component(hass, DOMAIN, {})
    granted = floor_registry.async_create("Upstairs", icon="mdi:home")
    floor_registry.async_create("Downstairs")

    user = MockUser(is_active=True, groups=[]).add_to_hass(hass)
    user.policy = {"entities": {"floor_ids": {granted.floor_id: {"read": True}}}}
    refresh_token = await hass.auth.async_create_refresh_token(user, CLIENT_ID)
    access_token = hass.auth.async_create_access_token(refresh_token)

    client = await hass_ws_client(hass, access_token)
    await client.send_json_auto_id({"type": "config/floor_registry/list"})
    msg = await client.receive_json()

    assert msg["success"], msg
    assert [floor["floor_id"] for floor in msg["result"]] == [granted.floor_id]
    assert msg["result"][0]["icon"] == "mdi:home"


async def test_update_floor_configure_right(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test the configure right allows floor edits without administrator."""
    assert await async_setup_component(hass, DOMAIN, {})
    floor = floor_registry.async_create("Upstairs")

    user = MockUser(is_active=True, groups=[]).add_to_hass(hass)
    user.policy = {
        "entities": {"floor_ids": {floor.floor_id: {"configure": True}}}
    }
    refresh_token = await hass.auth.async_create_refresh_token(user, CLIENT_ID)
    access_token = hass.auth.async_create_access_token(refresh_token)

    client = await hass_ws_client(hass, access_token)
    await client.send_json_auto_id(
        {
            "type": "config/floor_registry/update",
            "floor_id": floor.floor_id,
            "name": "Top floor",
        }
    )
    msg = await client.receive_json()
    assert msg["success"], msg
    assert msg["result"]["name"] == "Top floor"


async def test_update_floor_without_configure_denied(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test floor edits without the configure right stay blocked."""
    assert await async_setup_component(hass, DOMAIN, {})
    floor = floor_registry.async_create("Upstairs")

    user = MockUser(is_active=True, groups=[]).add_to_hass(hass)
    user.policy = {"entities": {"floor_ids": {floor.floor_id: {"read": True}}}}
    refresh_token = await hass.auth.async_create_refresh_token(user, CLIENT_ID)
    access_token = hass.auth.async_create_access_token(refresh_token)

    client = await hass_ws_client(hass, access_token)
    await client.send_json_auto_id(
        {
            "type": "config/floor_registry/update",
            "floor_id": floor.floor_id,
            "name": "Top floor",
        }
    )
    msg = await client.receive_json()
    assert not msg["success"], msg
