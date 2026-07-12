"""Tests for Kentix device discovery, hierarchy naming, and DoorLock UX."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from custom_components.kentix.models import KentixAlarmGroup, KentixDoorLock
from custom_components.kentix.naming import (
    alarm_group_depth,
    alarm_group_display_name,
    alarm_group_level_label,
    alarm_group_parent_identifier,
    door_lock_parent_identifier,
)

ROOT = Path(__file__).parents[1]


def _group(object_id: str, name: str, parent: str | None = None) -> KentixAlarmGroup:
    return KentixAlarmGroup(id=object_id, name=name, parent_group_id=parent)


def test_alarm_group_hierarchy_uses_requested_prefixes() -> None:
    groups = {
        "2": _group("2", "Bornstraße 23"),
        "3": _group("3", "Bornstr.", "2"),
        "1": _group("1", "Wohnung", "3"),
        "4": _group("4", "Serverraum", "1"),
    }

    assert alarm_group_display_name(groups["2"], groups) == "Standort - Bornstraße 23"
    assert alarm_group_display_name(groups["3"], groups) == "Gebäude - Bornstr."
    assert alarm_group_display_name(groups["1"], groups) == "Etage - Wohnung"
    assert alarm_group_display_name(groups["4"], groups) == "Bereich - Serverraum"


def test_alarm_group_depth_is_cycle_safe() -> None:
    groups = {
        "1": _group("1", "A", "2"),
        "2": _group("2", "B", "1"),
    }
    assert alarm_group_depth(groups["1"], groups) == 1
    assert alarm_group_level_label(groups["1"], groups) == "Gebäude"


def test_lock_platform_is_removed_in_favour_of_button() -> None:
    const_tree = ast.parse(
        (ROOT / "custom_components/kentix/const.py").read_text(encoding="utf-8")
    )
    source = ast.unparse(const_tree)
    assert "Platform.LOCK" not in source
    assert not (ROOT / "custom_components/kentix/lock.py").exists()


def test_door_release_is_not_option_gated() -> None:
    button_source = (ROOT / "custom_components/kentix/button.py").read_text(
        encoding="utf-8"
    )
    config_source = (ROOT / "custom_components/kentix/config_flow.py").read_text(
        encoding="utf-8"
    )
    assert "CONF_ENABLE_DOOR_CONTROL" not in button_source
    assert "enable_door_control" not in config_source


def test_release_button_wording_is_accurate() -> None:
    de = json.loads(
        (ROOT / "custom_components/kentix/translations/de.json").read_text(
            encoding="utf-8"
        )
    )
    assert de["entity"]["button"]["release_lock"]["name"] == "Schloss freigeben"
    assert "lock" not in de["entity"]


def test_device_registry_sync_is_wired_to_coordinator_updates() -> None:
    setup_source = (ROOT / "custom_components/kentix/__init__.py").read_text(
        encoding="utf-8"
    )
    assert "async_sync_devices(hass, entry, coordinator)" in setup_source
    assert "coordinator.async_add_listener" in setup_source
    assert "async_remove_legacy_lock_entities" in setup_source


def test_root_devices_do_not_require_a_synthetic_hub() -> None:
    root = _group("2", "Bornstraße 23")
    child = _group("3", "Bornstr.", "2")
    groups = {"2": root, "3": child}

    assert alarm_group_parent_identifier("entry", root, groups) is None
    assert alarm_group_parent_identifier("entry", child, groups) == (
        "kentix",
        "entry:alarm_group:2",
    )

    unassigned = KentixDoorLock(id="11", name="Eingangstüre")
    assigned = KentixDoorLock(
        id="12",
        name="Nebeneingang",
        parent_group_id="3",
    )
    assert door_lock_parent_identifier("entry", unassigned, groups) is None
    assert door_lock_parent_identifier("entry", assigned, groups) == (
        "kentix",
        "entry:alarm_group:3",
    )


def test_legacy_hub_device_cleanup_is_wired_during_setup() -> None:
    setup_source = (ROOT / "custom_components/kentix/__init__.py").read_text(
        encoding="utf-8"
    )
    entity_source = (ROOT / "custom_components/kentix/entity.py").read_text(
        encoding="utf-8"
    )
    assert "async_remove_legacy_hub_device(hass, entry)" in setup_source
    assert 'model="KentixONE"' not in setup_source
    assert 'model="KentixONE"' not in entity_source


def test_legacy_hub_cleanup_detaches_entities_and_removes_device(monkeypatch) -> None:
    from types import SimpleNamespace

    from custom_components.kentix import device_registry as registry_module

    hub = SimpleNamespace(id="hub-device")
    detached: list[tuple[str, str | None]] = []
    removed: list[str] = []

    class FakeDeviceRegistry:
        def async_get_device(self, *, identifiers):
            assert identifiers == {("kentix", "entry-id")}
            return hub

        def async_remove_device(self, device_id: str) -> None:
            removed.append(device_id)

    class FakeEntityRegistry:
        def async_update_entity(self, entity_id: str, *, device_id: str | None):
            detached.append((entity_id, device_id))

    entity_entries = [
        SimpleNamespace(entity_id="sensor.webhook_count", device_id="hub-device"),
        SimpleNamespace(entity_id="sensor.other", device_id="another-device"),
    ]

    monkeypatch.setattr(
        registry_module.dr, "async_get", lambda hass: FakeDeviceRegistry()
    )
    monkeypatch.setattr(
        registry_module.er, "async_get", lambda hass: FakeEntityRegistry()
    )
    monkeypatch.setattr(
        registry_module.er,
        "async_entries_for_config_entry",
        lambda registry, entry_id: entity_entries,
    )

    registry_module.async_remove_legacy_hub_device(
        SimpleNamespace(), SimpleNamespace(entry_id="entry-id")
    )

    assert detached == [("sensor.webhook_count", None)]
    assert removed == ["hub-device"]
