"""Kentix DoorLock entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_RAW_STATE, CONF_ENABLE_DOOR_CONTROL, DEFAULT_ENABLE_DOOR_CONTROL
from .discovery import async_setup_dynamic_entities
from .entity import KentixEntity
from .models import KentixDoorLock

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kentix DoorLocks."""
    coordinator = entry.runtime_data.coordinator
    if not entry.options.get(CONF_ENABLE_DOOR_CONTROL, DEFAULT_ENABLE_DOOR_CONTROL):
        return
    async_setup_dynamic_entities(
        entry,
        coordinator,
        async_add_entities,
        lambda: coordinator.data.door_locks,
        lambda door_lock: [KentixLock(coordinator, entry, door_lock)],
    )


class KentixLock(KentixEntity, LockEntity):
    """A Kentix DoorLock with remote-open support."""

    _attr_translation_key = "door_lock"
    _attr_supported_features = LockEntityFeature.OPEN

    def __init__(
        self, coordinator, entry: ConfigEntry, door_lock: KentixDoorLock
    ) -> None:
        super().__init__(coordinator, entry, "door_lock", door_lock.id, door_lock.name)

    @property
    def _door_lock(self) -> KentixDoorLock | None:
        return self.coordinator.data.door_locks.get(self._object_id)

    @property
    def available(self) -> bool:
        door_lock = self._door_lock
        return (
            super().available
            and self.coordinator.data.door_locks_available
            and door_lock is not None
            and door_lock.available is not False
        )

    @property
    def is_locked(self) -> bool | None:
        door_lock = self._door_lock
        return door_lock.is_locked if door_lock else None

    @property
    def is_open(self) -> bool | None:
        door_lock = self._door_lock
        return door_lock.is_open if door_lock else None

    @property
    def is_jammed(self) -> bool | None:
        door_lock = self._door_lock
        return door_lock.is_jammed if door_lock else None

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        door_lock = self._door_lock
        return {ATTR_RAW_STATE: door_lock.raw_state} if door_lock else {}

    async def async_open(self, **kwargs: Any) -> None:
        await self.coordinator.async_execute_command(
            lambda: self.coordinator.client.async_open_door_lock(self._object_id)
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        # Kentix remote unlock is a momentary release/open operation.
        await self.async_open(**kwargs)

    async def async_lock(self, **kwargs: Any) -> None:
        raise HomeAssistantError(
            "Kentix SmartAPI does not expose a persistent remote lock action"
        )
