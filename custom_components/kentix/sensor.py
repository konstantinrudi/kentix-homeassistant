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
from .models import KentixAlarmGroup, KentixDoorLock

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
        entities: list[SensorEntity] = []
        if door_lock.battery_level is not None:
            entities.append(KentixDoorBattery(coordinator, entry, door_lock))
        if door_lock.signal_strength is not None:
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
            and door_lock.available is not False
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
    _attr_entity_registry_enabled_default = False

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
