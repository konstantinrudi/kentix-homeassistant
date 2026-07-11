"""Kentix binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .discovery import async_setup_dynamic_entities
from .entity import KentixEntity, KentixHubEntity
from .models import KentixDoorLock

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kentix DoorLock binary sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            KentixAlarmApiConnectivity(coordinator, entry),
            KentixDoorApiConnectivity(coordinator, entry),
        ]
    )

    def factory(door_lock: KentixDoorLock) -> list[BinarySensorEntity]:
        entities: list[BinarySensorEntity] = []
        if door_lock.available is not None:
            entities.append(KentixDoorConnectivity(coordinator, entry, door_lock))
        if door_lock.is_open is not None:
            entities.append(KentixDoorContact(coordinator, entry, door_lock))
        return entities

    async_setup_dynamic_entities(
        entry,
        coordinator,
        async_add_entities,
        lambda: coordinator.data.door_locks,
        factory,
    )


class KentixDoorContact(KentixEntity, BinarySensorEntity):
    """Door contact state reported by a Kentix DoorLock."""

    _attr_translation_key = "door_contact"
    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(
        self, coordinator, entry: ConfigEntry, door_lock: KentixDoorLock
    ) -> None:
        super().__init__(
            coordinator,
            entry,
            "door_lock",
            door_lock.id,
            door_lock.name,
            entity_key="door_contact",
        )

    @property
    def _door_lock(self) -> KentixDoorLock | None:
        return self.coordinator.data.door_locks.get(self._object_id)

    @property
    def is_on(self) -> bool | None:
        door_lock = self._door_lock
        return door_lock.is_open if door_lock else None

    @property
    def available(self) -> bool:
        door_lock = self._door_lock
        return (
            super().available
            and self.coordinator.data.door_locks_available
            and door_lock is not None
            and door_lock.available is not False
            and door_lock.is_open is not None
        )


class KentixDoorConnectivity(KentixEntity, BinarySensorEntity):
    """Connectivity state of a Kentix DoorLock."""

    _attr_translation_key = "connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self, coordinator, entry: ConfigEntry, door_lock: KentixDoorLock
    ) -> None:
        super().__init__(
            coordinator,
            entry,
            "door_lock",
            door_lock.id,
            door_lock.name,
            entity_key="door_connectivity",
        )

    @property
    def _door_lock(self) -> KentixDoorLock | None:
        return self.coordinator.data.door_locks.get(self._object_id)

    @property
    def is_on(self) -> bool | None:
        door_lock = self._door_lock
        return door_lock.available if door_lock else None

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data.door_locks_available
            and self._door_lock is not None
        )


class KentixAlarmApiConnectivity(KentixHubEntity, BinarySensorEntity):
    """Availability of the alarm-group SmartAPI collection."""

    _attr_translation_key = "alarm_api_connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_alarm_api_connectivity"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.alarm_groups_available


class KentixDoorApiConnectivity(KentixHubEntity, BinarySensorEntity):
    """Availability of the DoorLock SmartAPI collection."""

    _attr_translation_key = "door_api_connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_door_api_connectivity"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.door_locks_available
