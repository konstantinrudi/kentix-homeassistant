"""Kentix action buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_ENABLE_DOOR_CONTROL, DEFAULT_ENABLE_DOOR_CONTROL
from .discovery import async_setup_dynamic_entities
from .entity import KentixEntity
from .models import KentixDoorLock

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kentix DoorLock buttons."""
    coordinator = entry.runtime_data.coordinator
    if not entry.options.get(CONF_ENABLE_DOOR_CONTROL, DEFAULT_ENABLE_DOOR_CONTROL):
        return
    async_setup_dynamic_entities(
        entry,
        coordinator,
        async_add_entities,
        lambda: coordinator.data.door_locks,
        lambda door_lock: [KentixOpenDoorButton(coordinator, entry, door_lock)],
    )


class KentixOpenDoorButton(KentixEntity, ButtonEntity):
    """Momentarily release/open a Kentix DoorLock."""

    _attr_translation_key = "open_door"
    _attr_icon = "mdi:door-open"

    def __init__(
        self, coordinator, entry: ConfigEntry, door_lock: KentixDoorLock
    ) -> None:
        super().__init__(
            coordinator,
            entry,
            "door_lock",
            door_lock.id,
            door_lock.name,
            entity_key="door_lock_open",
        )

    async def async_press(self) -> None:
        await self.coordinator.async_execute_command(
            lambda: self.coordinator.client.async_open_door_lock(self._object_id)
        )
