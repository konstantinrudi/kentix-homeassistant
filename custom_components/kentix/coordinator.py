"""Kentix data update coordinator."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    KentixApiClient,
    KentixApiError,
    KentixAuthenticationError,
    KentixConnectionError,
    KentixPermissionError,
    merge_alarm_group_runtime,
)
from .const import (
    ATTR_ENTRY_ID,
    ATTR_EVENT_ID,
    ATTR_EVENT_TYPE,
    ATTR_NEW_STATE,
    ATTR_OBJECT_ID,
    ATTR_OBJECT_NAME,
    ATTR_PREVIOUS_STATE,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_KENTIX_ALARM_CHANGED,
    EVENT_KENTIX_DOOR_CHANGED,
    EVENT_KENTIX_DOOR_OPENED,
    EVENT_KENTIX_WEBHOOK_RECEIVED,
    INVENTORY_REFRESH_INTERVAL,
    UNAVAILABLE_AFTER_FAILURES,
)
from .models import (
    KentixAlarmGroup,
    KentixData,
    KentixDoorLock,
    KentixRuntimeDevice,
    extract_runtime_devices,
    merge_runtime_devices,
)
from .naming import sort_alarm_groups
from .webhook_payload import parse_managed_webhook

_LOGGER = logging.getLogger(__name__)


class KentixDataUpdateCoordinator(DataUpdateCoordinator[KentixData]):
    """Coordinate lightweight state polling and infrequent inventory refreshes."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: KentixApiClient,
    ) -> None:
        scan_interval = int(
            entry.options.get(
                CONF_SCAN_INTERVAL,
                entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            )
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
            always_update=False,
        )
        self.client = client
        self.entry = entry
        self.last_webhook_received: datetime | None = None
        self.webhook_count = 0
        self.last_inventory_refresh: datetime | None = None
        self._alarm_groups: dict[str, KentixAlarmGroup] = {}
        self._door_locks: dict[str, KentixDoorLock] = {}
        self._runtime_devices: dict[str, KentixRuntimeDevice] = {}
        self._units: dict[str, str] = {}
        self._door_inventory_available = False
        self._webhook_group_timestamps: dict[str, int] = {}
        self.consecutive_update_failures = 0
        self.last_successful_update: datetime | None = None
        self.last_update_error: str | None = None
        self.last_valid_webhook_received: datetime | None = None
        self.invalid_webhook_count = 0
        self.last_webhook_error: str | None = None

    @property
    def integration_available(self) -> bool:
        """Keep entities available through short transient API outages."""
        return self.consecutive_update_failures < UNAVAILABLE_AFTER_FAILURES

    async def async_force_full_refresh(self) -> None:
        """Force system values and inventory to refresh immediately."""
        self.last_inventory_refresh = None
        await self.async_request_refresh()

    async def async_refresh_states(self) -> None:
        """Refresh only the shared runtime values endpoint now."""
        await self.async_request_refresh()

    async def async_rediscover_devices(self) -> None:
        """Refresh runtime values and all infrequent inventory collections now."""
        await self.async_force_full_refresh()

    async def _async_update_data(self) -> KentixData:
        previous = getattr(self, "data", None)
        now = dt_util.utcnow()
        refresh_inventory = (
            self.last_inventory_refresh is None
            or now - self.last_inventory_refresh >= INVENTORY_REFRESH_INTERVAL
        )

        system_values_task = asyncio.create_task(self.client.async_get_system_values())
        inventory_task = (
            asyncio.create_task(self._async_refresh_inventory(now))
            if refresh_inventory
            else None
        )

        try:
            system_values = await system_values_task
        except KentixAuthenticationError as err:
            await _async_cancel(inventory_task)
            self._note_update_failure(err)
            raise ConfigEntryAuthFailed from err
        except KentixConnectionError as err:
            await _async_cancel(inventory_task)
            self._note_update_failure(err)
            raise UpdateFailed(str(err)) from err
        except KentixApiError as err:
            await _async_cancel(inventory_task)
            self._note_update_failure(err)
            raise UpdateFailed(f"Kentix SmartAPI error: {err}") from err

        if inventory_task is not None:
            try:
                await inventory_task
            except KentixAuthenticationError as err:
                raise ConfigEntryAuthFailed from err

        self.consecutive_update_failures = 0
        self.last_update_error = None
        self.last_successful_update = now
        runtime_devices, units = extract_runtime_devices(system_values)
        self._runtime_devices = merge_runtime_devices(
            self._runtime_devices, runtime_devices
        )
        self._units = units or self._units
        door_locks = _merge_door_lock_runtime(self._door_locks, self._runtime_devices)
        current = KentixData(
            alarm_groups=sort_alarm_groups(
                merge_alarm_group_runtime(self._alarm_groups, system_values)
            ),
            door_locks=door_locks,
            devices=dict(self._runtime_devices),
            units=dict(self._units),
            alarm_groups_available=True,
            door_locks_available=self._door_inventory_available,
            devices_available=True,
        )
        if previous is not None:
            self._fire_change_events(previous, current)
        return current

    async def _async_refresh_inventory(self, refreshed_at: datetime) -> None:
        """Refresh discovery and DoorLock battery data at most every four hours."""
        # Mark the attempt immediately so a failed appliance is not hammered on every
        # normal state poll. A reload can still be used to force a fresh discovery.
        self.last_inventory_refresh = refreshed_at
        alarm_result, door_result = await asyncio.gather(
            self.client.async_get_alarm_group_inventory(),
            self.client.async_get_door_locks(),
            return_exceptions=True,
        )

        for result in (alarm_result, door_result):
            if isinstance(result, KentixAuthenticationError):
                raise result

        if isinstance(alarm_result, Exception):
            _LOGGER.warning(
                "Kentix alarm-group inventory refresh failed: %s", alarm_result
            )
        else:
            self._alarm_groups = alarm_result

        if isinstance(door_result, Exception):
            # Keep the last successful inventory and its telemetry available. A
            # transient four-hour refresh failure must not turn stable battery
            # values into unknown until the next successful request.
            self._door_inventory_available = bool(self._door_locks)
            _LOGGER.warning("Kentix DoorLock inventory refresh failed: %s", door_result)
        else:
            self._door_locks = _merge_door_lock_inventory(self._door_locks, door_result)
            self._door_inventory_available = True

    def _fire_change_events(self, previous: KentixData, current: KentixData) -> None:
        """Fire stable Home Assistant events for meaningful Kentix changes."""
        if current.alarm_groups_available:
            for object_id, group in current.alarm_groups.items():
                old = previous.alarm_groups.get(object_id)
                if old is None or old.event_state == group.event_state:
                    continue
                self.hass.bus.async_fire(
                    EVENT_KENTIX_ALARM_CHANGED,
                    {
                        ATTR_ENTRY_ID: self.entry.entry_id,
                        ATTR_OBJECT_ID: object_id,
                        ATTR_OBJECT_NAME: group.name,
                        ATTR_PREVIOUS_STATE: old.event_state,
                        ATTR_NEW_STATE: group.event_state,
                    },
                )

        if current.door_locks_available:
            for object_id, door_lock in current.door_locks.items():
                old = previous.door_locks.get(object_id)
                if old is None or old.event_state == door_lock.event_state:
                    continue
                event_data = {
                    ATTR_ENTRY_ID: self.entry.entry_id,
                    ATTR_OBJECT_ID: object_id,
                    ATTR_OBJECT_NAME: door_lock.name,
                    ATTR_PREVIOUS_STATE: old.event_state,
                    ATTR_NEW_STATE: door_lock.event_state,
                }
                self.hass.bus.async_fire(EVENT_KENTIX_DOOR_CHANGED, event_data)
                if old.is_open is not True and door_lock.is_open is True:
                    self.hass.bus.async_fire(EVENT_KENTIX_DOOR_OPENED, event_data)

    def _note_update_failure(self, err: Exception) -> None:
        self.consecutive_update_failures += 1
        self.last_update_error = type(err).__name__

    def async_note_invalid_webhook(self, reason: str) -> None:
        """Record a webhook payload that could not be applied directly."""
        self.invalid_webhook_count += 1
        self.last_webhook_error = reason
        self.async_update_listeners()

    def async_note_webhook(self, payload: Any) -> None:
        """Record a webhook notification and emit a privacy-conscious event."""
        self.last_webhook_received = dt_util.utcnow()
        self.webhook_count += 1
        event_id: str | None = None
        event_type: str | None = None
        if isinstance(payload, dict):
            for key in ("eventId", "event_id", "id"):
                if payload.get(key) is not None:
                    event_id = str(payload[key])
                    break
            for key in ("eventType", "event_type", "type", "status"):
                if payload.get(key) is not None:
                    event_type = str(payload[key])
                    break
        self.hass.bus.async_fire(
            EVENT_KENTIX_WEBHOOK_RECEIVED,
            {
                ATTR_ENTRY_ID: self.entry.entry_id,
                ATTR_EVENT_ID: event_id,
                ATTR_EVENT_TYPE: event_type,
            },
        )

    def async_apply_managed_webhook(self, payload: Any) -> bool:
        """Apply a validated state only to the group named by KentixONE."""
        update = parse_managed_webhook(payload)
        current_data = getattr(self, "data", None)
        if update is None:
            self.async_note_invalid_webhook(
                "Unrecognized or incomplete webhook payload"
            )
            return False
        if current_data is None or update.group_id not in current_data.alarm_groups:
            self.async_note_invalid_webhook("Webhook references an unknown alarm group")
            return False

        previous_timestamp = self._webhook_group_timestamps.get(update.group_id, -1)
        if update.timestamp is not None and update.timestamp < previous_timestamp:
            # A late duplicate is valid but must not roll a newer state back.
            return True

        group = current_data.alarm_groups[update.group_id]
        alarm_count = (
            update.alarm_count if update.alarm_count is not None else group.alarm_count
        )
        warning_count = (
            update.warning_count
            if update.warning_count is not None
            else group.warning_count
        )
        updated_group = replace(
            group,
            armed=update.armed,
            partially_armed=False,
            arming=False,
            disarming=False,
            raw_state="armed" if update.armed else "disarmed",
            alarm_count=alarm_count,
            warning_count=warning_count,
            triggered=(alarm_count > 0 if alarm_count is not None else group.triggered),
        )
        if update.timestamp is not None:
            self._webhook_group_timestamps[update.group_id] = update.timestamp

        groups = dict(current_data.alarm_groups)
        groups[update.group_id] = updated_group
        updated_data = replace(current_data, alarm_groups=sort_alarm_groups(groups))
        self.last_valid_webhook_received = dt_util.utcnow()
        self.last_webhook_error = None
        self._fire_change_events(current_data, updated_data)
        if updated_data == current_data:
            self.async_update_listeners()
        else:
            self.async_set_updated_data(updated_data)
        return True

    async def async_execute_command(
        self, command: Callable[[], Awaitable[None]]
    ) -> None:
        """Execute a Kentix command and turn transport failures into HA errors."""
        try:
            await command()
        except KentixAuthenticationError as err:
            self.entry.async_start_reauth_if_available(self.hass)
            raise HomeAssistantError("Kentix rejected the API token") from err
        except KentixPermissionError as err:
            raise HomeAssistantError(
                "The Kentix API user lacks permission for this action"
            ) from err
        except KentixConnectionError as err:
            raise HomeAssistantError("Kentix is currently unreachable") from err
        except KentixApiError as err:
            raise HomeAssistantError(f"Kentix command failed: {err}") from err
        # Command refreshes query only systemvalues unless the four-hour inventory
        # interval is due.
        await self.async_request_refresh()


def _merge_door_lock_inventory(
    previous: dict[str, KentixDoorLock],
    current: dict[str, KentixDoorLock],
) -> dict[str, KentixDoorLock]:
    """Keep last-known optional telemetry when Kentix omits it temporarily."""
    merged: dict[str, KentixDoorLock] = {}
    for object_id, door_lock in current.items():
        old = previous.get(object_id)
        if old is None:
            merged[object_id] = door_lock
            continue
        merged[object_id] = replace(
            door_lock,
            battery_level=(
                door_lock.battery_level
                if door_lock.battery_level is not None
                else old.battery_level
            ),
            signal_strength=(
                door_lock.signal_strength
                if door_lock.signal_strength is not None
                else old.signal_strength
            ),
            available=(
                door_lock.available
                if door_lock.available is not None
                else old.available
            ),
        )
    return merged


async def _async_cancel(task: asyncio.Task[Any] | None) -> None:
    """Cancel and drain a task created for a parallel inventory refresh."""
    if task is None or task.done():
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


def _merge_door_lock_runtime(
    inventory: dict[str, KentixDoorLock],
    devices: dict[str, KentixRuntimeDevice],
) -> dict[str, KentixDoorLock]:
    """Merge current `/api/systemvalues` telemetry into DoorLock inventory."""
    merged: dict[str, KentixDoorLock] = {}
    for object_id, door_lock in inventory.items():
        runtime = devices.get(object_id)
        if runtime is None:
            merged[object_id] = door_lock
            continue
        battery = runtime.measurement("battery_level")
        signal = runtime.measurement("signal_strength")
        reed = runtime.measurement("reed")
        merged[object_id] = replace(
            door_lock,
            battery_level=(
                battery.value
                if battery is not None and isinstance(battery.value, int)
                else door_lock.battery_level
            ),
            signal_strength=(
                signal.value
                if signal is not None and isinstance(signal.value, (int, float))
                else door_lock.signal_strength
            ),
            available=(
                runtime.available
                if runtime.available is not None
                else door_lock.available
            ),
            is_open=(
                reed.value
                if reed is not None and isinstance(reed.value, bool)
                else door_lock.is_open
            ),
        )
    return merged
