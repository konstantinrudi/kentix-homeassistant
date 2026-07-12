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
from .models import KentixDoorLock, KentixRuntimeDevice
from .visibility import runtime_device_visible

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
            KentixManagedWebhookConfigured(coordinator, entry),
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
    async_setup_dynamic_entities(
        entry,
        coordinator,
        async_add_entities,
        lambda: coordinator.data.devices,
        lambda device: _runtime_binary_factory(coordinator, entry, device),
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


_RUNTIME_BINARY_DESCRIPTORS = {
    "motion": ("motion", BinarySensorDeviceClass.MOTION),
    "reed": ("door_contact", BinarySensorDeviceClass.DOOR),
    "connection": ("connectivity", BinarySensorDeviceClass.CONNECTIVITY),
    "ext_power": ("external_power", BinarySensorDeviceClass.POWER),
    "vibration": ("vibration", BinarySensorDeviceClass.VIBRATION),
}


def _runtime_binary_factory(
    coordinator, entry: ConfigEntry, device: KentixRuntimeDevice
) -> list[BinarySensorEntity]:
    """Create enabled binary measurements for a runtime device."""
    if not runtime_device_visible(entry, device):
        return []
    entities: list[BinarySensorEntity] = []
    for key in _RUNTIME_BINARY_DESCRIPTORS:
        measurement = device.measurement(key)
        if measurement is None or not measurement.enabled:
            continue
        entities.append(KentixRuntimeBinarySensor(coordinator, entry, device, key))
    return entities


class KentixRuntimeBinarySensor(KentixEntity, BinarySensorEntity):
    """A boolean measurement from `/api/systemvalues`."""

    def __init__(
        self, coordinator, entry: ConfigEntry, device: KentixRuntimeDevice, key: str
    ) -> None:
        translation_key, device_class = _RUNTIME_BINARY_DESCRIPTORS[key]
        super().__init__(
            coordinator,
            entry,
            "runtime_device",
            device.id,
            device.name,
            entity_key=f"runtime_{key}",
        )
        self._measurement_key = key
        self._attr_translation_key = translation_key
        self._attr_device_class = device_class

    @property
    def _device(self) -> KentixRuntimeDevice | None:
        return self.coordinator.data.devices.get(self._object_id)

    @property
    def is_on(self) -> bool | None:
        device = self._device
        measurement = device.measurement(self._measurement_key) if device else None
        if measurement and isinstance(measurement.value, bool):
            return measurement.value
        return None

    @property
    def available(self) -> bool:
        device = self._device
        return (
            super().available
            and self.coordinator.data.devices_available
            and device is not None
            and (measurement := device.measurement(self._measurement_key)) is not None
            and measurement.enabled
            and (self._measurement_key == "connection" or device.available is not False)
        )


class KentixManagedWebhookConfigured(KentixHubEntity, BinarySensorEntity):
    """Whether automatic KentixONE webhook management is healthy."""

    _attr_translation_key = "managed_webhook"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_managed_webhook"

    @property
    def is_on(self) -> bool:
        manager = self._entry.runtime_data.webhook_manager
        return manager.configured if manager.enabled else False

    @property
    def extra_state_attributes(self) -> dict[str, str | bool | None]:
        manager = self._entry.runtime_data.webhook_manager
        return {
            "enabled": manager.enabled,
            "last_error": manager.last_error,
        }


class KentixAlarmApiConnectivity(KentixHubEntity, BinarySensorEntity):
    """Availability of the frequently polled system-values endpoint."""

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
    """Result of the most recent infrequent DoorLock inventory refresh."""

    _attr_translation_key = "door_api_connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_door_api_connectivity"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.door_locks_available
