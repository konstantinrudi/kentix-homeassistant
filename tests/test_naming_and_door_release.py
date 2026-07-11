"""Tests for Kentix device discovery, hierarchy naming, and DoorLock UX."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from custom_components.kentix.models import KentixAlarmGroup
from custom_components.kentix.naming import (
    alarm_group_depth,
    alarm_group_display_name,
    alarm_group_level_label,
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
