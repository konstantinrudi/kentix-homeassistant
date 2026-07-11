"""Synchronize Kentix objects with the Home Assistant device registry."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import KentixDataUpdateCoordinator
from .naming import (
    alarm_group_depth,
    alarm_group_display_name,
    alarm_group_parent_identifier,
    door_lock_parent_identifier,
)


@callback
def async_sync_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: KentixDataUpdateCoordinator,
) -> None:
    """Create or update every discovered Kentix device and its hierarchy."""
    registry = dr.async_get(hass)
    groups = coordinator.data.alarm_groups

    # Repeated passes are safe and make sure parent devices exist first where possible.
    for group in sorted(
        groups.values(), key=lambda item: alarm_group_depth(item, groups)
    ):
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}:alarm_group:{group.id}")},
            manufacturer="Kentix",
            model="Alarm Group",
            name=alarm_group_display_name(group, groups),
            via_device=alarm_group_parent_identifier(entry.entry_id, group, groups),
            configuration_url=coordinator.client.base_url,
        )

    for door_lock in coordinator.data.door_locks.values():
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}:door_lock:{door_lock.id}")},
            manufacturer="Kentix",
            model="DoorLock",
            name=door_lock.name,
            via_device=door_lock_parent_identifier(entry.entry_id, door_lock, groups),
            configuration_url=coordinator.client.base_url,
        )


@callback
def async_remove_legacy_lock_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Remove obsolete lock entities replaced by the stateless release button."""
    registry = er.async_get(hass)
    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if registry_entry.platform != DOMAIN:
            continue
        if not registry_entry.entity_id.startswith("lock."):
            continue
        registry.async_remove(registry_entry.entity_id)
