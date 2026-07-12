"""Automatic KentixONE webhook management."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .api import KentixApiClient, KentixApiError
from .const import (
    KENTIX_WEBHOOK_EVENT_ALL_ALARMS,
    KENTIX_WEBHOOK_EVENT_SWITCH_COMPLETE,
    KENTIX_WEBHOOK_EVENT_SYSTEM_ALARMS,
    KENTIX_WEBHOOK_NAME_PREFIX,
    KENTIX_WEBHOOK_SCHEMA,
    WEBHOOK_SYNC_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class KentixWebhookManager:
    """Create and maintain one KentixONE webhook owned by this config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: KentixApiClient,
        webhook_url: str,
        *,
        enabled: bool,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.client = client
        self.webhook_url = webhook_url
        self.enabled = enabled
        self.webhook_id: str | None = None
        self.configured = False
        self.last_error: str | None = None
        self._remove_interval = None
        self._known_group_ids: set[str] = set()

    @property
    def name(self) -> str:
        """Return a stable unique name for the managed webhook."""
        return f"{KENTIX_WEBHOOK_NAME_PREFIX} {self.entry.entry_id}"

    async def async_start(self) -> None:
        """Perform an initial sync and schedule infrequent reconciliation."""
        if not self.enabled:
            self.configured = False
            await self.async_delete_managed()
            return
        await self.async_ensure()
        self._remove_interval = async_track_time_interval(
            self.hass,
            self._async_periodic_sync,
            WEBHOOK_SYNC_INTERVAL,
        )
        self.entry.async_on_unload(self.async_stop)

    def async_stop(self) -> None:
        """Stop periodic reconciliation without deleting Kentix configuration."""
        if self._remove_interval is not None:
            self._remove_interval()
            self._remove_interval = None

    async def _async_periodic_sync(self, _now) -> None:
        await self.async_ensure()

    async def async_repair(self) -> None:
        """Force a full reconciliation of the managed webhook and assignments."""
        self._known_group_ids.clear()
        self.webhook_id = None
        await self.async_ensure()

    async def async_ensure(self) -> None:
        """Create/update the managed webhook and its alarm-group assignments."""
        if not self.enabled:
            self.configured = False
            return
        if not self.webhook_url.startswith(("http://", "https://")):
            self.configured = False
            self.last_error = (
                "Home Assistant has no absolute internal URL for KentixONE"
            )
            return
        try:
            webhook = await self._async_ensure_webhook()
            webhook_id = str(webhook["id"])
            force_assignments = self.webhook_id != webhook_id
            self.webhook_id = webhook_id
            await self._async_ensure_alarm_group_assignments(
                webhook_id, force=force_assignments
            )
        except (KentixApiError, KeyError, TypeError, ValueError) as err:
            self.configured = False
            self.last_error = str(err)
            _LOGGER.warning("Kentix automatic webhook setup failed: %s", err)
        else:
            self.configured = True
            self.last_error = None

    async def _async_ensure_webhook(self) -> dict:
        webhooks = await self.client.async_get_webhooks()
        current = next(
            (item for item in webhooks if str(item.get("name", "")) == self.name),
            None,
        )
        payload = {
            "is_active": True,
            "name": self.name,
            "request_type": 0,
            "content_type": 0,
            "url": self.webhook_url,
            "data": json.dumps(
                _managed_payload(),
                separators=(",", ":"),
            ),
            "authentication_mode": 0,
            "username": "",
            "password": "",
        }
        if current is None:
            return await self.client.async_create_webhook(payload)

        object_id = str(current["id"])
        needs_update = any(current.get(key) != value for key, value in payload.items())
        if needs_update:
            return await self.client.async_update_webhook(object_id, payload)
        return dict(current)

    async def _async_ensure_alarm_group_assignments(
        self, webhook_id: str, *, force: bool
    ) -> None:
        groups = await self.client.async_get_alarm_group_inventory()
        group_ids = set(groups)
        targets = group_ids if force else group_ids - self._known_group_ids
        desired = _desired_assignments(webhook_id)
        for group_id in targets:
            detail = await self.client.async_get_alarm_group_detail(group_id)
            current = detail.get("webhooks")
            assignments = (
                [
                    dict(item)
                    for item in current
                    if isinstance(item, Mapping)
                    and str(item.get("webhook_id")) != webhook_id
                ]
                if isinstance(current, list)
                else []
            )
            assignments.extend(desired)
            if _canonical_assignments(current) == _canonical_assignments(assignments):
                continue
            await self.client.async_set_alarm_group_webhooks(group_id, assignments)
        self._known_group_ids = group_ids

    async def async_delete_managed(self) -> None:
        """Remove owned assignments and the owned webhook, leaving others untouched."""
        try:
            webhooks = await self.client.async_get_webhooks()
            current = next(
                (item for item in webhooks if str(item.get("name", "")) == self.name),
                None,
            )
            if current is None:
                return
            webhook_id = str(current["id"])
            groups = await self.client.async_get_alarm_group_inventory()
            for group_id in groups:
                detail = await self.client.async_get_alarm_group_detail(group_id)
                current_assignments = detail.get("webhooks")
                if not isinstance(current_assignments, list):
                    continue
                filtered = [
                    dict(item)
                    for item in current_assignments
                    if isinstance(item, Mapping)
                    and str(item.get("webhook_id")) != webhook_id
                ]
                if len(filtered) != len(current_assignments):
                    await self.client.async_set_alarm_group_webhooks(group_id, filtered)
            await self.client.async_delete_webhook(webhook_id)
        except KentixApiError as err:
            _LOGGER.warning("Could not remove managed Kentix webhook: %s", err)


def _desired_assignments(webhook_id: str) -> list[dict]:
    return [
        {
            "webhook_id": int(webhook_id),
            "event": KENTIX_WEBHOOK_EVENT_ALL_ALARMS,
            "trigger_on_alarm": True,
            "trigger_on_warning": True,
            "cycle_time": None,
        },
        {
            "webhook_id": int(webhook_id),
            "event": KENTIX_WEBHOOK_EVENT_SYSTEM_ALARMS,
            "trigger_on_alarm": True,
            "trigger_on_warning": True,
            "cycle_time": None,
        },
        {
            "webhook_id": int(webhook_id),
            "event": KENTIX_WEBHOOK_EVENT_SWITCH_COMPLETE,
            "trigger_on_alarm": False,
            "trigger_on_warning": False,
            "cycle_time": None,
        },
    ]


def _canonical_assignments(value) -> list[tuple]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        result.append(
            (
                str(item.get("webhook_id")),
                item.get("event"),
                bool(item.get("trigger_on_alarm")),
                bool(item.get("trigger_on_warning")),
                repr(item.get("cycle_time")),
            )
        )
    return sorted(result)


def _managed_payload() -> dict[str, str]:
    """Return the versioned payload KentixONE sends to Home Assistant."""
    return {
        "schema": KENTIX_WEBHOOK_SCHEMA,
        "event_type": "group_state",
        "alarm_event_id": "$ALARM_EVENT_ID$",
        "group_id": "$GROUP_ID$",
        "group_state": "$GROUP_STATE$",
        "system_unixtime": "$SYSTEM_UNIXTIME$",
        "group_armed_alarm_count": "$GROUP_ARMED_ALARM_COUNT$",
        "group_armed_quitable_alarm_count": ("$GROUP_ARMED_QUITABLE_ALARM_COUNT$"),
        "group_armed_warning_count": "$GROUP_ARMED_WARNING_COUNT$",
        "group_armed_quitable_warning_count": ("$GROUP_ARMED_QUITABLE_WARNING_COUNT$"),
        "group_always_alarm_count": "$GROUP_ALWAYS_ALARM_COUNT$",
        "group_always_quitable_alarm_count": ("$GROUP_ALWAYS_QUITABLE_ALARM_COUNT$"),
        "group_always_warning_count": "$GROUP_ALWAYS_WARNING_COUNT$",
        "group_always_quitable_warning_count": (
            "$GROUP_ALWAYS_QUITABLE_WARNING_COUNT$"
        ),
        "group_fire_alarm_count": "$GROUP_FIRE_ALARM_COUNT$",
        "group_fire_quitable_alarm_count": "$GROUP_FIRE_QUITABLE_ALARM_COUNT$",
        "group_fire_warning_count": "$GROUP_FIRE_WARNING_COUNT$",
        "group_fire_quitable_warning_count": ("$GROUP_FIRE_QUITABLE_WARNING_COUNT$"),
        "group_sabotage_alarm_count": "$GROUP_SABOTAGE_ALARM_COUNT$",
        "group_sabotage_quitable_alarm_count": (
            "$GROUP_SABOTAGE_QUITABLE_ALARM_COUNT$"
        ),
        "group_sabotage_warning_count": "$GROUP_SABOTAGE_WARNING_COUNT$",
        "group_sabotage_quitable_warning_count": (
            "$GROUP_SABOTAGE_QUITABLE_WARNING_COUNT$"
        ),
        "group_system_alarm_count": "$GROUP_SYSTEM_ALARM_COUNT$",
        "group_system_quitable_alarm_count": ("$GROUP_SYSTEM_QUITABLE_ALARM_COUNT$"),
        "group_system_warning_count": "$GROUP_SYSTEM_WARNING_COUNT$",
        "group_system_quitable_warning_count": (
            "$GROUP_SYSTEM_QUITABLE_WARNING_COUNT$"
        ),
    }
