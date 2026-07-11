"""Base entities for Kentix."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KentixDataUpdateCoordinator


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
        physical_type = "alarm_group" if object_type == "alarm_group" else "door_lock"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}:{physical_type}:{object_id}")},
            name=object_name,
            manufacturer="Kentix",
            model="Alarm Group" if physical_type == "alarm_group" else "DoorLock",
            via_device=(DOMAIN, entry.entry_id),
            configuration_url=coordinator.client.base_url,
        )


class KentixHubEntity(CoordinatorEntity[KentixDataUpdateCoordinator]):
    """Base for hub-level entities."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: KentixDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Kentix",
            model="KentixONE",
            configuration_url=coordinator.client.base_url,
        )
