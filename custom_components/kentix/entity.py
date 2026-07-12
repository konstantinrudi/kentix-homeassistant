"""Base entities for Kentix."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KentixDataUpdateCoordinator
from .naming import (
    alarm_group_display_name,
    alarm_group_parent_identifier,
    door_lock_parent_identifier,
)


class KentixEntity(CoordinatorEntity[KentixDataUpdateCoordinator]):
    """Common Kentix entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KentixDataUpdateCoordinator,
        entry: ConfigEntry,
        object_type: str,
        object_id: str,
        object_name: str,
        *,
        entity_key: str | None = None,
    ) -> None:
        super().__init__(coordinator, context=f"{object_type}:{object_id}")
        self._entry = entry
        self._object_type = object_type
        self._object_id = object_id
        unique_type = entity_key or object_type
        self._attr_unique_id = f"{entry.entry_id}_{unique_type}_{object_id}"

        if object_type == "alarm_group":
            group = coordinator.data.alarm_groups.get(object_id)
            device_name = (
                alarm_group_display_name(group, coordinator.data.alarm_groups)
                if group is not None
                else object_name
            )
            via_device = (
                alarm_group_parent_identifier(
                    entry.entry_id, group, coordinator.data.alarm_groups
                )
                if group is not None
                else None
            )
            model = "Alarm Group"
            physical_type = "alarm_group"
            sw_version = None
        elif object_type == "runtime_device":
            device = coordinator.data.devices.get(object_id)
            device_name = device.name if device is not None else object_name
            model = device.model if device is not None else "Kentix device"
            sw_version = device.version if device is not None else None
            physical_type = "runtime_device"
            via_device = None
            if device is not None and device.parent_device_id:
                parent = coordinator.data.devices.get(device.parent_device_id)
                if parent is not None and parent.type_code != 21:
                    via_device = (
                        DOMAIN,
                        f"{entry.entry_id}:runtime_device:{parent.id}",
                    )
            if via_device is None and device is not None and device.parent_group_id:
                via_device = (
                    DOMAIN,
                    f"{entry.entry_id}:alarm_group:{device.parent_group_id}",
                )
        else:
            door_lock = coordinator.data.door_locks.get(object_id)
            device_name = door_lock.name if door_lock is not None else object_name
            via_device = (
                door_lock_parent_identifier(
                    entry.entry_id, door_lock, coordinator.data.alarm_groups
                )
                if door_lock is not None
                else None
            )
            model = "DoorLock"
            physical_type = "door_lock"
            sw_version = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}:{physical_type}:{object_id}")},
            name=device_name,
            manufacturer="Kentix",
            model=model,
            sw_version=sw_version,
            via_device=via_device,
            configuration_url=coordinator.client.base_url,
        )


class KentixHubEntity(CoordinatorEntity[KentixDataUpdateCoordinator]):
    """Base for integration-level entities without a synthetic device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: KentixDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
