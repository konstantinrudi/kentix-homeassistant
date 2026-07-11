"""Kentix data update coordinator."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
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
)
from .models import KentixData

_LOGGER = logging.getLogger(__name__)


class KentixDataUpdateCoordinator(DataUpdateCoordinator[KentixData]):
    """Coordinate polling and webhook-triggered refreshes of KentixONE."""

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

    async def _async_update_data(self) -> KentixData:
        previous = getattr(self, "data", None)
        try:
            current = await self.client.async_get_data()
        except KentixAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except KentixConnectionError as err:
            raise UpdateFailed(str(err)) from err
        except KentixApiError as err:
            raise UpdateFailed(f"Kentix SmartAPI error: {err}") from err

        if previous is not None:
            self._fire_change_events(previous, current)
        return current

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
        await self.async_request_refresh()
