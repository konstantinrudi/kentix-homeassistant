"""Visibility rules for optional Kentix device classes."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry

from .const import (
    ACCESS_MANAGER_TYPE_CODE,
    CONF_SHOW_ACCESS_MANAGERS,
    DEFAULT_SHOW_ACCESS_MANAGERS,
    DOOR_LOCK_TYPE_CODE,
)
from .models import KentixRuntimeDevice


def access_managers_visible(entry: ConfigEntry) -> bool:
    """Return whether AccessManager runtime devices should be exposed."""
    return bool(
        entry.options.get(CONF_SHOW_ACCESS_MANAGERS, DEFAULT_SHOW_ACCESS_MANAGERS)
    )


def runtime_device_visible(entry: ConfigEntry, device: KentixRuntimeDevice) -> bool:
    """Return whether a runtime device should be represented in Home Assistant."""
    if device.type_code == DOOR_LOCK_TYPE_CODE:
        # DoorLocks have their own dedicated device and action entity.
        return False
    if device.type_code == ACCESS_MANAGER_TYPE_CODE:
        return access_managers_visible(entry)
    return True
