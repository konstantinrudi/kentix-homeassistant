"""Kentix action buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .discovery import async_setup_dynamic_entities
from .entity import KentixEntity, KentixHubEntity
from .models import KentixDoorLock

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kentix DoorLock release buttons."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            KentixRepairWebhookButton(coordinator, entry),
            KentixRefreshStatesButton(coordinator, entry),
            KentixRediscoverDevicesButton(coordinator, entry),
        ]
    )
    async_setup_dynamic_entities(
        entry,
        coordinator,
        async_add_entities,
        lambda: coordinator.data.door_locks,
        lambda door_lock: [KentixReleaseLockButton(coordinator, entry, door_lock)],
    )


class KentixReleaseLockButton(KentixEntity, ButtonEntity):
    """Momentarily enable manual rotation of a Kentix DoorLock."""

    _attr_translation_key = "release_lock"
    _attr_icon = "mdi:lock-open-variant"

    def __init__(
        self, coordinator, entry: ConfigEntry, door_lock: KentixDoorLock
    ) -> None:
        super().__init__(
            coordinator,
            entry,
            "door_lock",
            door_lock.id,
            door_lock.name,
            # Preserve the existing button unique ID across the rename.
            entity_key="door_lock_open",
        )

    async def async_press(self) -> None:
        await self.coordinator.async_execute_command(
            lambda: self.coordinator.client.async_release_door_lock(self._object_id)
        )


class KentixRepairWebhookButton(KentixHubEntity, ButtonEntity):
    """Reconcile the managed KentixONE webhook and all assignments."""

    _attr_translation_key = "repair_webhook"
    _attr_icon = "mdi:webhook"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_repair_webhook"

    async def async_press(self) -> None:
        await self._entry.runtime_data.webhook_manager.async_repair()
        self.coordinator.async_update_listeners()


class KentixRefreshStatesButton(KentixHubEntity, ButtonEntity):
    """Refresh the shared Kentix runtime values now."""

    _attr_translation_key = "refresh_states"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        # Preserve the existing unique ID across the clearer rename.
        self._attr_unique_id = f"{entry.entry_id}_refresh_data"

    async def async_press(self) -> None:
        await self.coordinator.async_refresh_states()


class KentixRediscoverDevicesButton(KentixHubEntity, ButtonEntity):
    """Force Kentix inventory discovery instead of waiting four hours."""

    _attr_translation_key = "rediscover_devices"
    _attr_icon = "mdi:database-search"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_rediscover_devices"

    async def async_press(self) -> None:
        await self.coordinator.async_rediscover_devices()
