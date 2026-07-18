"""Synchronize Kentix objects with the Home Assistant device registry."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import KentixDataUpdateCoordinator
from .naming import (
    alarm_group_display_name,
    alarm_group_parent_identifier,
    alarm_group_sort_key,
    door_lock_parent_identifier,
)
from .visibility import runtime_device_visible


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
        groups.values(), key=lambda item: alarm_group_sort_key(item, groups)
    ):
        parent_identifier = alarm_group_parent_identifier(entry.entry_id, group, groups)
        device = registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}:alarm_group:{group.id}")},
            manufacturer="Kentix",
            model="Alarm Group",
            name=alarm_group_display_name(group, groups),
            via_device=parent_identifier,
            configuration_url=coordinator.client.base_url,
        )
        if parent_identifier is None and device.via_device_id is not None:
            registry.async_update_device(device.id, via_device_id=None)

    runtime_devices = coordinator.data.devices
    for runtime in runtime_devices.values():
        if not runtime_device_visible(entry, runtime, coordinator.data.door_locks):
            continue
        via_device = None
        if runtime.parent_device_id:
            parent = runtime_devices.get(runtime.parent_device_id)
            if parent is not None and runtime_device_visible(
                entry, parent, coordinator.data.door_locks
            ):
                via_device = (
                    DOMAIN,
                    f"{entry.entry_id}:runtime_device:{parent.id}",
                )
        if via_device is None and runtime.parent_group_id:
            via_device = (
                DOMAIN,
                f"{entry.entry_id}:alarm_group:{runtime.parent_group_id}",
            )
        device = registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}:runtime_device:{runtime.id}")},
            manufacturer="Kentix",
            model=runtime.model,
            name=runtime.name,
            sw_version=runtime.version,
            via_device=via_device,
            configuration_url=coordinator.client.base_url,
        )
        if via_device is None and device.via_device_id is not None:
            registry.async_update_device(device.id, via_device_id=None)

    _async_remove_hidden_runtime_devices(
        registry,
        er.async_get(hass),
        entry,
        runtime_devices,
        coordinator.data.door_locks,
    )

    for door_lock in coordinator.data.door_locks.values():
        parent_identifier = door_lock_parent_identifier(
            entry.entry_id, door_lock, groups
        )
        device = registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}:door_lock:{door_lock.id}")},
            manufacturer="Kentix",
            model="DoorLock",
            name=door_lock.name,
            via_device=parent_identifier,
            configuration_url=coordinator.client.base_url,
        )
        if parent_identifier is None and device.via_device_id is not None:
            registry.async_update_device(device.id, via_device_id=None)


@callback
def _async_remove_hidden_runtime_devices(
    registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    entry: ConfigEntry,
    runtime_devices,
    door_locks,
) -> None:
    """Remove previously exposed runtime devices that are now filtered out."""
    for runtime in runtime_devices.values():
        if runtime_device_visible(entry, runtime, door_locks):
            continue
        device = registry.async_get_device(
            identifiers={(DOMAIN, f"{entry.entry_id}:runtime_device:{runtime.id}")}
        )
        if device is None:
            continue
        for registry_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if registry_entry.device_id == device.id:
                entity_registry.async_remove(registry_entry.entity_id)
        registry.async_remove_device(device.id)


@callback
def async_remove_legacy_hub_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Remove the synthetic KentixONE hub device used by older releases."""
    device_registry = dr.async_get(hass)
    hub_device = device_registry.async_get_device(
        identifiers={(DOMAIN, entry.entry_id)}
    )
    if hub_device is None:
        return

    entity_registry = er.async_get(hass)
    for registry_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if registry_entry.device_id == hub_device.id:
            entity_registry.async_update_entity(
                registry_entry.entity_id,
                device_id=None,
            )

    device_registry.async_remove_device(hub_device.id)


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
