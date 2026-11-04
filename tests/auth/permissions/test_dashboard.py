"""Tests for dashboard hiding based on readable entities."""

from homeassistant.auth import models
from homeassistant.auth.permissions.dashboard import (
    dashboard_has_readable_entity,
    extract_dashboard_entities,
)


def test_extract_dashboard_entities() -> None:
    """Test entity identifiers are found in views and cards."""
    config = {
        "views": [
            {
                "cards": [
                    {"type": "entities", "entities": ["light.a", "Not an entity"]},
                    {"type": "entity", "entity": "light.b"},
                    {
                        "type": "custom",
                        "elements": [{"entity": "light.c"}],
                    },
                ]
            }
        ]
    }
    assert extract_dashboard_entities(config) == {"light.a", "light.b", "light.c"}


def test_extract_dashboard_entities_ignores_text() -> None:
    """Test card titles without dots never count as entities."""
    config = {"views": [{"title": "Home", "cards": [{"title": "No entities"}]}]}
    assert extract_dashboard_entities(config) == set()


class _StubDashboard:
    """Minimal dashboard config stub for readability checks."""

    def __init__(self, config: dict | None) -> None:
        self._config = config

    async def async_load(self, force: bool) -> dict:
        if self._config is None:
            raise ValueError("No config")
        return self._config


async def test_dashboard_without_entities_stays_visible() -> None:
    """Test strategy and empty dashboards are never hidden."""
    user = models.User(
        name="Test",
        perm_lookup=None,
        groups=[],
        policy={"entities": {}},
    )
    assert (
        await dashboard_has_readable_entity(_StubDashboard({"views": []}), user)
        is True
    )
    assert (
        await dashboard_has_readable_entity(_StubDashboard(None), user) is True
    )


async def test_dashboard_hides_without_readable_entity() -> None:
    """Test dashboards hide when no listed entity is readable."""
    user = models.User(
        name="Test",
        perm_lookup=None,
        groups=[],
        policy={"entities": {"entity_ids": {"light.a": {"read": True}}}},
    )
    readable = _StubDashboard(
        {"views": [{"cards": [{"entities": ["light.a", "light.b"]}]}]}
    )
    hidden = _StubDashboard({"views": [{"cards": [{"entity": "light.b"}]}]})
    assert await dashboard_has_readable_entity(readable, user) is True
    assert await dashboard_has_readable_entity(hidden, user) is False
