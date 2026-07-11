"""Diagnostics support for Kentix."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import CONF_API_TOKEN, CONF_WEBHOOK_ID


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics without site names, IDs, users, tokens, or raw data."""
    data = dict(entry.data)
    host = str(data.get(CONF_HOST, ""))
    data[CONF_HOST] = "**REDACTED**"
    data[CONF_API_TOKEN] = "**REDACTED**"
    if CONF_WEBHOOK_ID in data:
        data[CONF_WEBHOOK_ID] = "**REDACTED**"

    coordinator = entry.runtime_data.coordinator
    snapshot = coordinator.data
    return {
        "config_entry": {
            "title": "**REDACTED**",
            "data": data,
            "options": dict(entry.options),
            "host_scheme": urlparse(host).scheme or None,
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_webhook_received": (
                coordinator.last_webhook_received.isoformat()
                if coordinator.last_webhook_received
                else None
            ),
            "webhook_count": coordinator.webhook_count,
            "alarm_groups_available": snapshot.alarm_groups_available,
            "door_locks_available": snapshot.door_locks_available,
            "alarm_group_count": len(snapshot.alarm_groups),
            "door_lock_count": len(snapshot.door_locks),
        },
        "alarm_group_capabilities": [
            {
                "armed_known": group.armed is not None,
                "partial_arm": group.partially_armed,
                "arming": group.arming,
                "disarming": group.disarming,
                "triggered": group.triggered,
                "alarm_count_supported": group.alarm_count is not None,
                "warning_count_supported": group.warning_count is not None,
                "raw_state": group.raw_state,
                "changed_by_available": group.last_changed_by is not None,
            }
            for group in snapshot.alarm_groups.values()
        ],
        "door_lock_capabilities": [
            {
                "lock_state_known": door_lock.is_locked is not None,
                "door_contact_supported": door_lock.is_open is not None,
                "jammed": door_lock.is_jammed,
                "available": door_lock.available,
                "battery_supported": door_lock.battery_level is not None,
                "signal_strength_supported": door_lock.signal_strength is not None,
                "raw_state": door_lock.raw_state,
            }
            for door_lock in snapshot.door_locks.values()
        ],
    }
