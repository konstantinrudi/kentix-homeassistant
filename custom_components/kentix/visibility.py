"""Visibility rules for optional Kentix device classes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry

from .const import CONF_SHOW_ACCESS_MANAGERS, DEFAULT_SHOW_ACCESS_MANAGERS
from .models import KentixDoorLock, KentixRuntimeDevice

# KentixONE uses multiple runtime type codes for lock cylinders/readers depending
# on hardware generation. These devices are already represented by the dedicated
# DoorLock inventory and must not be created a second time from systemvalues.
KNOWN_DOOR_LOCK_RUNTIME_TYPE_CODES = {21, 25, 26, 28}


def access_managers_visible(entry: ConfigEntry) -> bool:
    """Return whether AccessManager runtime devices should be exposed."""
    return bool(
        entry.options.get(CONF_SHOW_ACCESS_MANAGERS, DEFAULT_SHOW_ACCESS_MANAGERS)
    )


def runtime_device_visible(
    entry: ConfigEntry,
    device: KentixRuntimeDevice,
    door_locks: Mapping[str, KentixDoorLock] | None = None,
) -> bool:
    """Return whether a runtime device should be represented in Home Assistant."""
    locks = door_locks or {}
    if _runtime_is_dedicated_door_lock(device, locks):
        return False
    if _runtime_is_access_manager(device, locks):
        return access_managers_visible(entry)
    return True


def _runtime_is_dedicated_door_lock(
    device: KentixRuntimeDevice,
    door_locks: Mapping[str, KentixDoorLock],
) -> bool:
    """Return whether runtime data belongs to an already represented DoorLock."""
    if device.type_code in KNOWN_DOOR_LOCK_RUNTIME_TYPE_CODES:
        return True
    return device.id in door_locks


def _runtime_is_access_manager(
    device: KentixRuntimeDevice,
    door_locks: Mapping[str, KentixDoorLock],
) -> bool:
    """Detect AccessManager hosts from DoorLock inventory, not one fixed type code."""
    if device.type_code == 105:
        return True
    controller_ids = {
        controller_id
        for lock in door_locks.values()
        if (controller_id := _door_lock_controller_id(lock)) is not None
    }
    return device.id in controller_ids


def _door_lock_controller_id(lock: KentixDoorLock) -> str | None:
    """Extract the AccessManager/controller ID from firmware-specific payloads."""
    raw: Mapping[str, Any] = lock.raw
    for key in ("device_id", "accessmanager_id", "access_manager_id", "host_id"):
        value = raw.get(key)
        if value is not None:
            return str(value)
    host = raw.get("host")
    if isinstance(host, Mapping) and host.get("id") is not None:
        return str(host["id"])
    return None
