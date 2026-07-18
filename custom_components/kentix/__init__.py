"""Kentix integration setup."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial

from homeassistant.components import webhook as ha_webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError

from .api import KentixApiClient
from .const import (
    CONF_API_TOKEN,
    CONF_MANAGE_WEBHOOK,
    CONF_SHOW_ACCESS_MANAGERS,
    CONF_VERIFY_SSL,
    CONF_WEBHOOK_ID,
    DEFAULT_MANAGE_WEBHOOK,
    DEFAULT_SHOW_ACCESS_MANAGERS,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import KentixDataUpdateCoordinator
from .device_registry import (
    async_remove_legacy_hub_device,
    async_remove_legacy_lock_entities,
    async_sync_devices,
)
from .webhook_handler import async_handle_webhook
from .webhook_manager import KentixWebhookManager

type KentixConfigEntry = ConfigEntry["KentixRuntimeData"]


@dataclass(slots=True)
class KentixRuntimeData:
    """Runtime objects stored on the config entry."""

    client: KentixApiClient
    coordinator: KentixDataUpdateCoordinator
    webhook_id: str
    webhook_url: str
    webhook_manager: KentixWebhookManager


async def async_setup_entry(hass: HomeAssistant, entry: KentixConfigEntry) -> bool:
    """Set up Kentix from a config entry."""
    if CONF_SHOW_ACCESS_MANAGERS not in entry.options:
        hass.config_entries.async_update_entry(
            entry,
            options={
                **entry.options,
                CONF_SHOW_ACCESS_MANAGERS: DEFAULT_SHOW_ACCESS_MANAGERS,
            },
        )

    webhook_id = entry.data.get(CONF_WEBHOOK_ID)
    if not webhook_id:
        webhook_id = ha_webhook.async_generate_id()
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_WEBHOOK_ID: webhook_id},
        )

    client = KentixApiClient(
        async_get_clientsession(
            hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
        ),
        entry.data[CONF_HOST],
        entry.data[CONF_API_TOKEN],
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
    )
    coordinator = KentixDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    try:
        webhook_url = ha_webhook.async_generate_url(
            hass,
            webhook_id,
            allow_internal=True,
            allow_external=False,
            prefer_external=False,
        )
    except NoURLAvailableError:
        webhook_url = ha_webhook.async_generate_path(webhook_id)

    webhook_manager = KentixWebhookManager(
        hass,
        entry,
        client,
        webhook_url,
        enabled=entry.options.get(CONF_MANAGE_WEBHOOK, DEFAULT_MANAGE_WEBHOOK),
    )
    entry.runtime_data = KentixRuntimeData(
        client=client,
        coordinator=coordinator,
        webhook_id=webhook_id,
        webhook_url=webhook_url,
        webhook_manager=webhook_manager,
    )

    ha_webhook.async_register(
        hass,
        DOMAIN,
        entry.title,
        webhook_id,
        partial(async_handle_webhook, coordinator=coordinator),
        local_only=True,
        allowed_methods={"POST", "PUT"},
    )
    entry.async_on_unload(lambda: ha_webhook.async_unregister(hass, webhook_id))
    await webhook_manager.async_start()

    # Every Kentix object is automatically represented in the HA device registry,
    # even when it currently has no optional sensor entity.
    async_sync_devices(hass, entry, coordinator)
    async_remove_legacy_hub_device(hass, entry)
    entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: async_sync_devices(hass, entry, coordinator)
        )
    )

    # v0.3 replaces the misleading lock entity with one stateless release button.
    async_remove_legacy_lock_entities(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KentixConfigEntry) -> bool:
    """Unload a Kentix config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: KentixConfigEntry) -> None:
    """Remove only the Kentix webhook owned by this config entry."""
    client = KentixApiClient(
        async_get_clientsession(
            hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
        ),
        entry.data[CONF_HOST],
        entry.data[CONF_API_TOKEN],
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
    )
    webhook_id = entry.data.get(CONF_WEBHOOK_ID, "")
    webhook_url = ha_webhook.async_generate_path(webhook_id) if webhook_id else ""
    manager = KentixWebhookManager(
        hass,
        entry,
        client,
        webhook_url,
        enabled=True,
    )
    await manager.async_delete_managed()


async def _async_update_listener(hass: HomeAssistant, entry: KentixConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
