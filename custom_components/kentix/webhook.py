"""Kentix webhook receiver."""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp.web import Request, Response
from homeassistant.core import HomeAssistant

from .coordinator import KentixDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
MAX_WEBHOOK_SIZE = 256 * 1024


async def async_handle_webhook(
    hass: HomeAssistant,
    webhook_id: str,
    request: Request,
    coordinator: KentixDataUpdateCoordinator,
) -> Response:
    """Handle a KentixONE notification and refresh state from the API."""
    payload: Any = None
    try:
        body = await request.content.read(MAX_WEBHOOK_SIZE + 1)
        if len(body) > MAX_WEBHOOK_SIZE:
            _LOGGER.warning("Ignored oversized Kentix webhook payload")
            return Response(status=413)
        if body:
            try:
                payload = json.loads(body)
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = None
    except OSError:
        payload = None

    coordinator.async_note_webhook(payload)
    hass.async_create_task(
        coordinator.async_request_refresh(),
        "Refresh Kentix after webhook",
    )
    return Response(status=200)
