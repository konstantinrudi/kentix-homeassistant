"""Kentix integration setup."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KentixApiClient
from .const import (
    CONF_API_TOKEN,
    CONF_VERIFY_SSL,
    CONF_WEBHOOK_ID,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import KentixDataUpdateCoordinator
from .webhook import async_handle_webhook

type KentixConfigEntry = ConfigEntry["KentixRuntimeData"]


@dataclass(slots=True)
class KentixRuntimeData:
    """Runtime objects stored on the config entry."""

    client: KentixApiClient
    coordinator: KentixDataUpdateCoordinator
    webhook_id: str
    webhook_url: str


async def async_setup_entry(hass: HomeAssistant, entry: KentixConfigEntry) -> bool:
    """Set up Kentix from a config entry."""
    webhook_id = entry.data.get(CONF_WEBHOOK_ID)
    if not webhook_id:
        webhook_id = webhook.async_generate_id()
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
        webhook_url = webhook.async_generate_url(
            hass,
            webhook_id,
            allow_internal=True,
            allow_external=False,
            prefer_external=False,
        )
    except Exception:  # Home Assistant may not have an internal URL configured.
        webhook_url = webhook.async_generate_path(webhook_id)

    entry.runtime_data = KentixRuntimeData(
        client=client,
        coordinator=coordinator,
        webhook_id=webhook_id,
        webhook_url=webhook_url,
    )

    webhook.async_register(
        hass,
        DOMAIN,
        entry.title,
        webhook_id,
        partial(async_handle_webhook, coordinator=coordinator),
        local_only=True,
        allowed_methods={"POST", "PUT"},
    )
    entry.async_on_unload(lambda: webhook.async_unregister(hass, webhook_id))

    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Kentix",
        model="KentixONE",
        name=entry.title,
        configuration_url=client.base_url,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KentixConfigEntry) -> bool:
    """Unload a Kentix config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: KentixConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
