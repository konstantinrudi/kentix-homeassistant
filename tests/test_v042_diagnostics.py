"""v0.4.2 diagnostics, version, and sorting regression tests."""

import json
from pathlib import Path

from custom_components.kentix.models import KentixAlarmGroup, KentixRuntimeDevice
from custom_components.kentix.naming import sort_alarm_groups
from custom_components.kentix.versioning import (
    detect_kentixone_version,
    detect_smartapi_version,
    normalize_kentix_version,
)


def test_version_normalization_and_detection() -> None:
    devices = {
        "5": KentixRuntimeDevice(
            id="5", name="Controller", type_code=101, version="08.06.02 B01579"
        )
    }
    assert normalize_kentix_version("08.06.02 B01579") == "8.6.2 B01579"
    assert detect_kentixone_version(devices) == "8.6.2 B01579"
    assert detect_smartapi_version(devices) == "8.6"


def test_alarm_groups_are_sorted_by_hierarchy_path() -> None:
    groups = {
        "3": KentixAlarmGroup(id="3", name="Etage Z", parent_group_id="2"),
        "1": KentixAlarmGroup(id="1", name="Standort"),
        "4": KentixAlarmGroup(id="4", name="Etage A", parent_group_id="2"),
        "2": KentixAlarmGroup(id="2", name="Gebäude", parent_group_id="1"),
    }
    assert list(sort_alarm_groups(groups)) == ["1", "2", "4", "3"]


def test_v042_translations_and_access_manager_description() -> None:
    data = json.loads(Path("custom_components/kentix/translations/de.json").read_text())
    assert "health_status" in data["entity"]["sensor"]
    assert "rediscover_devices" in data["entity"]["button"]
    description = data["options"]["step"]["init"]["data_description"][
        "show_access_managers"
    ]
    assert "DoorLocks" in description
    assert "bleiben vollständig sichtbar" in description
