"""Helpers to hide dashboards without readable content."""

from typing import Any

from homeassistant.auth.permissions.const import POLICY_READ

if False:  # Type checking only; avoids runtime imports.
    from homeassistant.auth.models import User

__all__ = [
    "dashboard_has_readable_entity",
    "extract_dashboard_entities",
]

_ENTITY_KEYS = {"entity", "entities", "entity_id", "entity_ids", "camera_image"}


def extract_dashboard_entities(config: dict[str, Any] | list[Any]) -> set[str]:
    """Collect entity identifiers from a dashboard configuration.

    Walks views and cards recursively. Only values shaped like entity
    identifiers (containing a dot) are kept, so card titles and other
    text never count as entities.
    """
    found: set[str] = set()
    _walk(config, found)
    return found


def _walk(node: Any, found: set[str]) -> None:
    """Recursively collect entity identifiers from one node."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _ENTITY_KEYS:
                found.update(_as_entity_ids(value))
            _walk(value, found)
    elif isinstance(node, list):
        for item in node:
            _walk(item, found)


def _as_entity_ids(value: Any) -> set[str]:
    """Normalize one entity field to entity identifiers."""
    if isinstance(value, str):
        return {value} if "." in value else set()
    if isinstance(value, list):
        ids: set[str] = set()
        for item in value:
            if isinstance(item, str) and "." in item:
                ids.add(item)
        return ids
    return set()


async def dashboard_has_readable_entity(
    dashboard_config: Any, user: User
) -> bool:
    """Return True when a dashboard shows at least one readable entity.

    Dashboards without static entities (strategy or empty dashboards)
    stay visible, since their content cannot be judged statically.
    Dashboards whose config cannot load also stay visible.
    """
    try:
        config = await dashboard_config.async_load(False)
    except Exception:  # noqa: BLE001 - missing config stays visible.
        return True
    entities = extract_dashboard_entities(config)
    if not entities:
        return True
    check_entity = user.permissions.check_entity
    return any(check_entity(entity_id, POLICY_READ) for entity_id in entities)
