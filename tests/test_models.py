"""Tests for Kentix response normalization without importing Home Assistant."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
PACKAGE_PATH = ROOT / "custom_components" / "kentix"

package = types.ModuleType("custom_components.kentix")
package.__path__ = [str(PACKAGE_PATH)]
sys.modules.setdefault("custom_components.kentix", package)


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, PACKAGE_PATH / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


models = _load_module("custom_components.kentix.models", "models.py")
api = _load_module("custom_components.kentix.api", "api.py")

KentixAlarmGroup = models.KentixAlarmGroup
KentixData = models.KentixData
KentixDoorLock = models.KentixDoorLock
KentixApiClient = api.KentixApiClient
KentixAuthenticationError = api.KentixAuthenticationError
KentixPermissionError = api.KentixPermissionError
extract_items = api.extract_items
extract_system_alarm_groups = api.extract_system_alarm_groups
merge_alarm_group_runtime = api.merge_alarm_group_runtime
normalize_host = api.normalize_host


def test_normalize_host() -> None:
    assert normalize_host("192.168.1.50") == "https://192.168.1.50"
    assert normalize_host("https://kentix.local/") == "https://kentix.local"


def test_extract_items_from_envelope() -> None:
    payload = {"data": [{"id": 1, "name": "Server room"}]}
    assert extract_items(payload) == [{"id": 1, "name": "Server room"}]


def test_extract_single_object() -> None:
    payload = {"id": 7, "name": "Only group", "armed": True}
    assert extract_items(payload) == [payload]


def test_extract_items_from_id_name_mapping() -> None:
    payload = {"data": {"12": "Office", "13": "Warehouse"}}
    assert extract_items(payload) == [
        {"id": "12", "name": "Office"},
        {"id": "13", "name": "Warehouse"},
    ]


def test_normalize_host_preserves_reverse_proxy_path() -> None:
    assert normalize_host("https://kentix.local/security/") == (
        "https://kentix.local/security"
    )


def test_normalize_host_rejects_embedded_credentials() -> None:
    with pytest.raises(ValueError):
        normalize_host("https://admin:secret@kentix.local")


def test_alarm_group_normalization() -> None:
    group = KentixAlarmGroup.from_payload(
        {"id": 3, "name": "Office", "switching_status": "armed"}
    )
    assert group.id == "3"
    assert group.armed is True
    assert group.triggered is False


def test_camel_case_nested_alarm_group_normalization() -> None:
    group = KentixAlarmGroup.from_payload(
        {
            "alarmGroupId": 4,
            "name": "Lobby",
            "status": {"switchingStatus": "partially armed", "alarmCount": 0},
        }
    )
    assert group.id == "4"
    assert group.partially_armed is True
    assert group.alarm_count == 0


def test_triggered_alarm_has_priority_data() -> None:
    group = KentixAlarmGroup.from_payload(
        {"id": "7", "name": "Rack", "armed": True, "alarm_active": True}
    )
    assert group.armed is True
    assert group.triggered is True
    assert group.event_state == "triggered"


def test_door_lock_normalization() -> None:
    door = KentixDoorLock.from_payload(
        {"doorlock_id": 9, "name": "Front door", "door_open": False}
    )
    assert door.id == "9"
    assert door.is_open is False


def test_camel_case_door_battery_and_connectivity() -> None:
    door = KentixDoorLock.from_payload(
        {
            "doorLockId": 9,
            "deviceName": "Front door",
            "online": False,
            "batteryLevel": "87%",
            "rssi": -71,
        }
    )
    assert door.available is False
    assert door.battery_level == 87
    assert door.signal_strength == -71


@pytest.mark.asyncio
async def test_authentication_failure_is_global() -> None:
    client = object.__new__(KentixApiClient)

    async def alarm_groups():
        raise KentixAuthenticationError("invalid token")

    async def door_locks():
        return {"1": KentixDoorLock(id="1", name="Door")}

    client.async_get_alarm_groups = alarm_groups
    client.async_get_door_locks = door_locks

    with pytest.raises(KentixAuthenticationError):
        await client.async_get_data()


@pytest.mark.asyncio
async def test_partial_permission_error_still_returns_other_collection() -> None:
    client = object.__new__(KentixApiClient)

    async def alarm_groups():
        return {"1": KentixAlarmGroup(id="1", name="Alarm")}

    async def door_locks():
        raise KentixPermissionError("not permitted")

    client.async_get_alarm_groups = alarm_groups
    client.async_get_door_locks = door_locks

    data = await client.async_get_data()
    assert data.alarm_groups_available is True
    assert data.door_locks_available is False
    assert "1" in data.alarm_groups


@pytest.mark.asyncio
async def test_sparse_alarm_group_list_does_not_request_details() -> None:
    client = object.__new__(KentixApiClient)
    client._routes = api.KentixRoutes()
    requested: list[str] = []

    async def request_collection_candidates(routes):
        return [{"id": "12", "name": "Office"}]

    async def request(method, route):
        requested.append(route)
        assert route == "/api/systemvalues"
        return {"alarmgroups": [{"name": "Office", "armed": True}]}

    client._request_collection_candidates = request_collection_candidates
    client._request = request

    groups = await client.async_get_alarm_groups()
    assert groups["12"].name == "Office"
    assert groups["12"].armed is True
    assert requested == ["/api/systemvalues"]


@pytest.mark.asyncio
async def test_dense_door_collection_does_not_request_details() -> None:
    client = object.__new__(KentixApiClient)
    client._routes = api.KentixRoutes()

    async def request_collection_candidates(routes):
        return [{"id": "7", "name": "Front", "doorOpen": False}]

    async def request(method, route):
        raise AssertionError("detail route must not be called for a dense item")

    client._request_collection_candidates = request_collection_candidates
    client._request = request

    doors = await client.async_get_door_locks()
    assert doors["7"].is_open is False


def test_real_kentix_doorlock_collection_payload() -> None:
    door = KentixDoorLock.from_payload(
        {
            "batterylevel": "full",
            "device_id": 10,
            "id": 11,
            "is_active": True,
            "name": "Entrance",
            "type": 21,
            "group_id": 1,
        }
    )
    assert door.id == "11"
    assert door.name == "Entrance"
    assert door.battery_level == 100


def test_real_kentix_alarmgroup_collection_envelope() -> None:
    payload = {
        "data": [
            {"id": 1, "name": "Apartment", "group_id": 3, "sort_index": 1},
            {"id": 2, "name": "Building", "group_id": None, "sort_index": 1},
        ],
        "links": {"next": None},
        "meta": {"current_page": 1, "total": 2},
    }
    assert extract_items(payload) == payload["data"]


@pytest.mark.asyncio
async def test_paginated_collection_is_combined() -> None:
    client = object.__new__(KentixApiClient)
    pages = {
        "/api/alarmgroups": {
            "data": [{"id": 1, "name": "One"}],
            "links": {"next": "https://kentix.local/api/alarmgroups?page=2"},
        },
        "https://kentix.local/api/alarmgroups?page=2": {
            "data": [{"id": 2, "name": "Two"}],
            "links": {"next": None},
        },
    }

    async def request(method, route):
        assert method == "GET"
        return pages[route]

    client._request = request
    payload = await client._request_paginated("/api/alarmgroups")
    assert [item["id"] for item in payload["data"]] == [1, 2]


def test_real_alarmgroup_detail_is_configuration_not_runtime_state() -> None:
    group = KentixAlarmGroup.from_payload(
        {
            "id": 1,
            "name": "Area",
            "group_id": 3,
            "maintenance": "inactive",
            "has_prealarm": True,
            "arm_delay": 10,
            "event_id": None,
        }
    )
    assert group.parent_group_id == "3"
    assert group.arm_delay == 10
    assert group.has_prealarm is True
    assert group.maintenance == "inactive"
    assert group.armed is None
    assert group.triggered is False


def test_real_doorlock_detail_does_not_fake_connectivity_or_contact() -> None:
    door = KentixDoorLock.from_payload(
        {
            "id": 11,
            "name": "Entrance",
            "group_id": 1,
            "arm_group_id": 3,
            "is_active": True,
            "reed_assignment": "off",
            "reed_source_id": None,
            "connection": {"assignment": "display", "warning": {"active": True}},
        }
    )
    assert door.parent_group_id == "1"
    assert door.arm_group_id == "3"
    assert door.enabled is True
    assert door.has_door_contact is False
    assert door.available is None
    assert door.is_open is None
    assert door.is_locked is None


def test_extract_systemvalues_alarmgroups_top_level() -> None:
    payload = {
        "alarmgroups": [
            {"name": "Building", "armed": False},
            {"name": "Office", "armed": True},
        ]
    }
    assert extract_system_alarm_groups(payload) == payload["alarmgroups"]


def test_extract_systemvalues_alarmgroups_nested_envelope() -> None:
    payload = {"data": {"alarm_groups": [{"id": 3, "armed": True}]}}
    assert extract_system_alarm_groups(payload) == [{"id": 3, "armed": True}]


def test_merge_systemvalues_runtime_by_name() -> None:
    groups = {
        "2": KentixAlarmGroup.from_payload(
            {"id": 2, "name": "Bornstraße 23", "group_id": None, "arm_delay": 10}
        )
    }
    merged = merge_alarm_group_runtime(
        groups, {"alarmgroups": [{"name": "Bornstraße 23", "armed": True}]}
    )
    assert merged["2"].armed is True
    assert merged["2"].raw_state == "armed"
    assert merged["2"].arm_delay == 10


def test_merge_systemvalues_runtime_prefers_id() -> None:
    groups = {
        "1": KentixAlarmGroup(id="1", name="Duplicate"),
        "2": KentixAlarmGroup(id="2", name="Duplicate"),
    }
    merged = merge_alarm_group_runtime(
        groups, {"alarmgroups": [{"id": 2, "name": "Duplicate", "armed": False}]}
    )
    assert merged["1"].armed is None
    assert merged["2"].armed is False


def test_duplicate_names_without_id_are_not_guessed() -> None:
    groups = {
        "1": KentixAlarmGroup(id="1", name="Duplicate"),
        "2": KentixAlarmGroup(id="2", name="Duplicate"),
    }
    merged = merge_alarm_group_runtime(
        groups, {"alarmgroups": [{"name": "Duplicate", "armed": True}]}
    )
    assert merged["1"].armed is None
    assert merged["2"].armed is None


@pytest.mark.asyncio
async def test_alarm_groups_merge_systemvalues_runtime() -> None:
    client = object.__new__(KentixApiClient)
    client._routes = api.KentixRoutes()

    async def collection(routes):
        return [{"id": 2, "name": "Bornstraße 23", "armed": False}]

    async def request(method, route):
        assert method == "GET"
        assert route == "/api/systemvalues"
        return {"alarmgroups": [{"name": "Bornstraße 23", "armed": True}]}

    client._request_collection_candidates = collection
    client._request = request
    groups = await client.async_get_alarm_groups()
    assert groups["2"].armed is True


@pytest.mark.asyncio
async def test_release_door_lock_uses_put_request() -> None:
    client = object.__new__(KentixApiClient)
    client._routes = api.KentixRoutes()
    calls: list[tuple[str, str]] = []

    async def request(method, route):
        calls.append((method, route))
        return None

    client._request = request
    await client.async_release_door_lock("11")

    assert calls == [("PUT", "/api/doorlocks/11/open")]
