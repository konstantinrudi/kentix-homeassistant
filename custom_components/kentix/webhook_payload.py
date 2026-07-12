"""Validated direct-state payloads sent by managed KentixONE webhooks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .const import KENTIX_WEBHOOK_SCHEMA

_ALARM_COUNT_FIELDS = (
    "group_armed_alarm_count",
    "group_armed_quitable_alarm_count",
    "group_always_alarm_count",
    "group_always_quitable_alarm_count",
    "group_fire_alarm_count",
    "group_fire_quitable_alarm_count",
    "group_sabotage_alarm_count",
    "group_sabotage_quitable_alarm_count",
    "group_system_alarm_count",
    "group_system_quitable_alarm_count",
)

_WARNING_COUNT_FIELDS = (
    "group_armed_warning_count",
    "group_armed_quitable_warning_count",
    "group_always_warning_count",
    "group_always_quitable_warning_count",
    "group_fire_warning_count",
    "group_fire_quitable_warning_count",
    "group_sabotage_warning_count",
    "group_sabotage_quitable_warning_count",
    "group_system_warning_count",
    "group_system_quitable_warning_count",
)


@dataclass(frozen=True, slots=True)
class KentixWebhookGroupUpdate:
    """A validated group-state update from a managed KentixONE webhook."""

    group_id: str
    armed: bool
    timestamp: int | None = None
    alarm_count: int | None = None
    warning_count: int | None = None
    event_id: str | None = None


def parse_managed_webhook(payload: Any) -> KentixWebhookGroupUpdate | None:
    """Parse only the versioned payload owned by this integration."""
    if not isinstance(payload, Mapping):
        return None
    if payload.get("schema") != KENTIX_WEBHOOK_SCHEMA:
        return None

    group_id = _resolved_text(payload.get("group_id"))
    state = _zero_or_one(payload.get("group_state"))
    if group_id is None or state is None:
        return None

    timestamp = _integer(payload.get("system_unixtime"))
    if timestamp is not None and timestamp > 10_000_000_000:
        timestamp //= 1000

    return KentixWebhookGroupUpdate(
        group_id=group_id,
        armed=bool(state),
        timestamp=timestamp,
        alarm_count=_sum_fields(payload, _ALARM_COUNT_FIELDS),
        warning_count=_sum_fields(payload, _WARNING_COUNT_FIELDS),
        event_id=_resolved_text(payload.get("alarm_event_id")),
    )


def _sum_fields(payload: Mapping[str, Any], fields: tuple[str, ...]) -> int | None:
    values: list[int] = []
    for field in fields:
        value = _integer(payload.get(field))
        if value is not None:
            values.append(max(0, value))
    return sum(values) if values else None


def _resolved_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or (text.startswith("$") and text.endswith("$")):
        return None
    return text


def _integer(value: Any) -> int | None:
    text = _resolved_text(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _zero_or_one(value: Any) -> int | None:
    parsed = _integer(value)
    return parsed if parsed in {0, 1} else None
