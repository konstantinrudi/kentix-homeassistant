"""Tests for the split Kentix runtime and inventory schedules."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.util import dt as dt_util

from custom_components.kentix.coordinator import KentixDataUpdateCoordinator
from custom_components.kentix.models import KentixAlarmGroup, KentixDoorLock


class FakeClient:
    """Count calls made by the coordinator."""

    def __init__(self) -> None:
        self.system_calls = 0
        self.alarm_inventory_calls = 0
        self.door_inventory_calls = 0

    async def async_get_system_values(self):
        self.system_calls += 1
        return {"alarmgroups": [{"id": 1, "name": "Site", "armed": False}]}

    async def async_get_alarm_group_inventory(self):
        self.alarm_inventory_calls += 1
        return {"1": KentixAlarmGroup(id="1", name="Site")}

    async def async_get_door_locks(self):
        self.door_inventory_calls += 1
        return {"11": KentixDoorLock(id="11", name="Entrance", battery_level=100)}


@pytest.mark.asyncio
async def test_normal_poll_only_reads_systemvalues() -> None:
    client = FakeClient()
    coordinator = object.__new__(KentixDataUpdateCoordinator)
    coordinator.client = client
    coordinator.last_inventory_refresh = None
    coordinator._alarm_groups = {}
    coordinator._door_locks = {}
    coordinator._door_inventory_available = False

    first = await coordinator._async_update_data()
    assert client.system_calls == 1
    assert client.alarm_inventory_calls == 1
    assert client.door_inventory_calls == 1
    assert first.door_locks["11"].battery_level == 100

    coordinator.data = first
    coordinator.last_inventory_refresh = dt_util.utcnow() - timedelta(hours=1)
    second = await coordinator._async_update_data()

    assert client.system_calls == 2
    assert client.alarm_inventory_calls == 1
    assert client.door_inventory_calls == 1
    assert second.alarm_groups["1"].armed is False


@pytest.mark.asyncio
async def test_door_battery_keeps_last_successful_value_when_omitted() -> None:
    coordinator = object.__new__(KentixDataUpdateCoordinator)
    coordinator._door_locks = {
        "11": KentixDoorLock(id="11", name="Entrance", battery_level=100)
    }
    coordinator._door_inventory_available = True

    class ClientWithoutBattery(FakeClient):
        async def async_get_door_locks(self):
            self.door_inventory_calls += 1
            return {"11": KentixDoorLock(id="11", name="Entrance")}

    coordinator.client = ClientWithoutBattery()
    await coordinator._async_refresh_inventory(dt_util.utcnow())

    assert coordinator._door_locks["11"].battery_level == 100
    assert coordinator._door_inventory_available is True


@pytest.mark.asyncio
async def test_door_battery_stays_available_after_transient_inventory_failure() -> None:
    coordinator = object.__new__(KentixDataUpdateCoordinator)
    coordinator._door_locks = {
        "11": KentixDoorLock(id="11", name="Entrance", battery_level=100)
    }
    coordinator._alarm_groups = {}
    coordinator._door_inventory_available = True

    class FailingDoorClient(FakeClient):
        async def async_get_door_locks(self):
            self.door_inventory_calls += 1
            raise RuntimeError("temporary failure")

    coordinator.client = FailingDoorClient()
    await coordinator._async_refresh_inventory(dt_util.utcnow())

    assert coordinator._door_locks["11"].battery_level == 100
    assert coordinator._door_inventory_available is True


@pytest.mark.asyncio
async def test_door_signal_keeps_last_successful_value_when_omitted() -> None:
    coordinator = object.__new__(KentixDataUpdateCoordinator)
    coordinator._door_locks = {
        "11": KentixDoorLock(
            id="11", name="Entrance", battery_level=100, signal_strength=-71
        )
    }
    coordinator._door_inventory_available = True

    class ClientWithoutSignal(FakeClient):
        async def async_get_door_locks(self):
            self.door_inventory_calls += 1
            return {"11": KentixDoorLock(id="11", name="Entrance", battery_level=100)}

    coordinator.client = ClientWithoutSignal()
    await coordinator._async_refresh_inventory(dt_util.utcnow())

    assert coordinator._door_locks["11"].signal_strength == -71
    assert coordinator._door_inventory_available is True
