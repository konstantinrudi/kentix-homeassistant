"""Kentix numeric sensors."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .discovery import async_setup_dynamic_entities
from .entity import KentixEntity, KentixHubEntity
from .models import KentixAlarmGroup, KentixDoorLock, KentixRuntimeDevice
from .versioning import detect_kentixone_version, detect_smartapi_version
from .visibility import runtime_device_visible

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kentix sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            KentixWebhookCount(coordinator, entry),
            KentixLastWebhook(coordinator, entry),
            KentixLastValidWebhook(coordinator, entry),
            KentixInvalidWebhookCount(coordinator, entry),
            KentixHealthStatus(coordinator, entry),
            KentixOneVersion(coordinator, entry),
            KentixSmartApiVersion(coordinator, entry),
        ]
    )

    def alarm_factory(group: KentixAlarmGroup) -> list[SensorEntity]:
        entities: list[SensorEntity] = []
        if group.alarm_count is not None:
            entities.append(KentixAlarmCount(coordinator, entry, group))
        if group.warning_count is not None:
            entities.append(KentixWarningCount(coordinator, entry, group))
        return entities

    def door_factory(door_lock: KentixDoorLock) -> list[SensorEntity]:
        # Always create the battery entity for discovered DoorLocks. Some KentixONE
        # responses omit telemetry temporarily or expose it only on a later inventory
        # refresh. The entity can then move from unknown to the first reported value
        # without requiring an integration reload.
        entities: list[SensorEntity] = [
            KentixDoorBattery(coordinator, entry, door_lock)
        ]
        entities.append(KentixDoorSignalStrength(coordinator, entry, door_lock))
        return entities

    async_setup_dynamic_entities(
        entry,
        coordinator,
        async_add_entities,
        lambda: coordinator.data.alarm_groups,
        alarm_factory,
    )
    async_setup_dynamic_entities(
        entry,
        coordinator,
        async_add_entities,
        lambda: coordinator.data.door_locks,
        door_factory,
    )
    async_setup_dynamic_entities(
        entry,
        coordinator,
        async_add_entities,
        lambda: coordinator.data.devices,
        lambda device: _runtime_sensor_factory(coordinator, entry, device),
    )


class KentixAlarmMetric(KentixEntity, SensorEntity):
    """Base class for alarm-group counters."""

    _attr_native_unit_of_measurement = "events"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False

    @property
    def _group(self) -> KentixAlarmGroup | None:
        return self.coordinator.data.alarm_groups.get(self._object_id)

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data.alarm_groups_available
            and self._group is not None
        )


class KentixAlarmCount(KentixAlarmMetric):
    """Pending alarm count."""

    _attr_translation_key = "alarm_count"

    def __init__(
        self, coordinator, entry: ConfigEntry, group: KentixAlarmGroup
    ) -> None:
        super().__init__(
            coordinator,
            entry,
            "alarm_group",
            group.id,
            group.name,
            entity_key="alarm_count",
        )

    @property
    def native_value(self) -> int | None:
        group = self._group
        return group.alarm_count if group else None


class KentixWarningCount(KentixAlarmMetric):
    """Pending warning count."""

    _attr_translation_key = "warning_count"

    def __init__(
        self, coordinator, entry: ConfigEntry, group: KentixAlarmGroup
    ) -> None:
        super().__init__(
            coordinator,
            entry,
            "alarm_group",
            group.id,
            group.name,
            entity_key="warning_count",
        )

    @property
    def native_value(self) -> int | None:
        group = self._group
        return group.warning_count if group else None


class KentixDoorMetric(KentixEntity, SensorEntity):
    """Base class for DoorLock diagnostic sensors."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

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
        )


class KentixDoorBattery(KentixDoorMetric):
    """DoorLock battery level."""

    _attr_translation_key = "battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, coordinator, entry: ConfigEntry, door_lock: KentixDoorLock
    ) -> None:
        super().__init__(
            coordinator,
            entry,
            "door_lock",
            door_lock.id,
            door_lock.name,
            entity_key="door_battery",
        )

    @property
    def native_value(self) -> int | None:
        door_lock = self._door_lock
        return door_lock.battery_level if door_lock else None


class KentixDoorSignalStrength(KentixDoorMetric):
    """DoorLock radio signal strength."""

    _attr_translation_key = "signal_strength"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT

    def __init__(
        self, coordinator, entry: ConfigEntry, door_lock: KentixDoorLock
    ) -> None:
        super().__init__(
            coordinator,
            entry,
            "door_lock",
            door_lock.id,
            door_lock.name,
            entity_key="door_signal_strength",
        )

    @property
    def native_value(self) -> float | None:
        door_lock = self._door_lock
        return door_lock.signal_strength if door_lock else None


_RUNTIME_SENSOR_DESCRIPTORS = {
    "temperature": ("temperature", SensorDeviceClass.TEMPERATURE),
    "humidity": ("humidity", SensorDeviceClass.HUMIDITY),
    "dewpoint": ("dewpoint", SensorDeviceClass.TEMPERATURE),
    "co": ("carbon_monoxide", SensorDeviceClass.CO),
    "co2": ("carbon_dioxide", SensorDeviceClass.CO2),
    "pressure": ("pressure", SensorDeviceClass.ATMOSPHERIC_PRESSURE),
    "battery_level": ("battery", SensorDeviceClass.BATTERY),
    "signal_strength": ("signal_strength", SensorDeviceClass.SIGNAL_STRENGTH),
}


def _runtime_sensor_factory(
    coordinator, entry: ConfigEntry, device: KentixRuntimeDevice
) -> list[SensorEntity]:
    """Create numeric entities exposed and enabled by one runtime device."""
    if not runtime_device_visible(entry, device, coordinator.data.door_locks):
        return []
    entities: list[SensorEntity] = []
    for key in _RUNTIME_SENSOR_DESCRIPTORS:
        measurement = device.measurement(key)
        if measurement is None or not measurement.enabled:
            continue
        entities.append(KentixRuntimeSensor(coordinator, entry, device, key))
    return entities


class KentixRuntimeSensor(KentixEntity, SensorEntity):
    """A numeric measurement from `/api/systemvalues`."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator, entry: ConfigEntry, device: KentixRuntimeDevice, key: str
    ) -> None:
        translation_key, device_class = _RUNTIME_SENSOR_DESCRIPTORS[key]
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
    def native_value(self):
        device = self._device
        measurement = device.measurement(self._measurement_key) if device else None
        return measurement.value if measurement else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        device = self._device
        measurement = device.measurement(self._measurement_key) if device else None
        if measurement is None:
            return None
        if self._measurement_key == "battery_level":
            return PERCENTAGE
        if self._measurement_key == "signal_strength":
            return SIGNAL_STRENGTH_DECIBELS_MILLIWATT
        return measurement.unit

    @property
    def available(self) -> bool:
        device = self._device
        return (
            super().available
            and self.coordinator.data.devices_available
            and device is not None
            and (measurement := device.measurement(self._measurement_key)) is not None
            and measurement.enabled
            and (
                self._measurement_key in {"battery_level", "signal_strength"}
                or device.available is not False
            )
        )


class KentixWebhookCount(KentixHubEntity, SensorEntity):
    """Number of Kentix webhooks received since the integration loaded."""

    _attr_translation_key = "webhook_count"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_native_unit_of_measurement = "events"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_webhook_count"

    @property
    def native_value(self) -> int:
        return self.coordinator.webhook_count


class KentixLastWebhook(KentixHubEntity, SensorEntity):
    """Timestamp of the last Kentix webhook received."""

    _attr_translation_key = "last_webhook"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_webhook"

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.last_webhook_received


class KentixLastValidWebhook(KentixHubEntity, SensorEntity):
    """Timestamp of the last directly validated state webhook."""

    _attr_translation_key = "last_valid_webhook"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_valid_webhook"

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.last_valid_webhook_received


class KentixInvalidWebhookCount(KentixHubEntity, SensorEntity):
    """Number of webhook payloads that required API fallback."""

    _attr_translation_key = "invalid_webhook_count"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_native_unit_of_measurement = "events"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_invalid_webhook_count"

    @property
    def native_value(self) -> int:
        return self.coordinator.invalid_webhook_count


class KentixHealthStatus(KentixHubEntity, SensorEntity):
    """Central diagnostic overview for this Kentix config entry."""

    _attr_translation_key = "health_status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:heart-pulse"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_health_status"

    @property
    def native_value(self) -> str:
        manager = self._entry.runtime_data.webhook_manager
        if not self.coordinator.integration_available:
            return "unavailable"
        if self.coordinator.consecutive_update_failures or (
            manager.enabled and not manager.configured
        ):
            return "degraded"
        return "healthy"

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        data = self.coordinator.data
        manager = self._entry.runtime_data.webhook_manager
        return {
            "kentixone_version": detect_kentixone_version(data.devices),
            "smartapi_version": detect_smartapi_version(data.devices),
            "smartapi_version_source": "derived_from_kentixone_version",
            "systemvalues_available": data.alarm_groups_available,
            "doorlock_inventory_available": data.door_locks_available,
            "managed_webhook_enabled": manager.enabled,
            "managed_webhook_configured": manager.configured,
            "managed_webhook_error": manager.last_error,
            "last_successful_update": (
                self.coordinator.last_successful_update.isoformat()
                if self.coordinator.last_successful_update
                else None
            ),
            "last_webhook_received": (
                self.coordinator.last_webhook_received.isoformat()
                if self.coordinator.last_webhook_received
                else None
            ),
            "last_valid_state_webhook": (
                self.coordinator.last_valid_webhook_received.isoformat()
                if self.coordinator.last_valid_webhook_received
                else None
            ),
            "consecutive_api_failures": self.coordinator.consecutive_update_failures,
            "alarm_groups": len(data.alarm_groups),
            "door_locks": len(data.door_locks),
            "runtime_devices": len(data.devices),
            "update_interval_seconds": (
                int(self.coordinator.update_interval.total_seconds())
                if self.coordinator.update_interval
                else None
            ),
        }


class KentixOneVersion(KentixHubEntity, SensorEntity):
    """Detected KentixONE controller software version."""

    _attr_translation_key = "kentixone_version"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:package-variant-closed"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_kentixone_version"

    @property
    def native_value(self) -> str | None:
        return detect_kentixone_version(self.coordinator.data.devices)


class KentixSmartApiVersion(KentixHubEntity, SensorEntity):
    """SmartAPI compatibility profile derived from KentixONE version."""

    _attr_translation_key = "smartapi_version"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:api"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_smartapi_version"

    @property
    def native_value(self) -> str | None:
        return detect_smartapi_version(self.coordinator.data.devices)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {"source": "derived_from_kentixone_version"}
