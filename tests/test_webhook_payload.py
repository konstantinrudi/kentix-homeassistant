"""Tests for direct managed-webhook state handling."""

from __future__ import annotations

from custom_components.kentix.coordinator import (
    KentixDataUpdateCoordinator,
)
from custom_components.kentix.models import KentixAlarmGroup, KentixData
from custom_components.kentix.webhook_payload import parse_managed_webhook


def _payload(**overrides):
    payload = {
        "schema": "kentix_home_assistant_v2",
        "event_type": "group_state",
        "group_id": "2",
        "group_state": "1",
        "system_unixtime": "1783843200",
        "group_armed_alarm_count": "1",
        "group_armed_quitable_alarm_count": "2",
        "group_always_warning_count": "3",
        "alarm_event_id": "91",
    }
    payload.update(overrides)
    return payload


def test_managed_webhook_parser_extracts_state_and_counts() -> None:
    update = parse_managed_webhook(_payload())
    assert update is not None
    assert update.group_id == "2"
    assert update.armed is True
    assert update.timestamp == 1783843200
    assert update.alarm_count == 3
    assert update.warning_count == 3
    assert update.event_id == "91"


def test_managed_webhook_parser_rejects_unknown_schema_or_state() -> None:
    assert parse_managed_webhook(_payload(schema="unknown")) is None
    assert parse_managed_webhook(_payload(group_state="2")) is None
    assert parse_managed_webhook(_payload(group_id="$GROUP_ID$")) is None


def _coordinator(groups: dict[str, KentixAlarmGroup]):
    coordinator = object.__new__(KentixDataUpdateCoordinator)
    coordinator.data = KentixData(alarm_groups=groups, door_locks={})
    coordinator._webhook_group_timestamps = {}
    coordinator._fire_change_events = lambda previous, current: None
    coordinator.async_set_updated_data = lambda data: setattr(coordinator, "data", data)
    coordinator.async_update_listeners = lambda: None
    return coordinator


def test_webhook_updates_only_reported_group() -> None:
    coordinator = _coordinator(
        {
            "1": KentixAlarmGroup(
                id="1", name="Floor", parent_group_id="3", armed=False
            ),
            "2": KentixAlarmGroup(id="2", name="Site", armed=False),
            "3": KentixAlarmGroup(
                id="3", name="Building", parent_group_id="2", armed=False
            ),
        }
    )

    assert coordinator.async_apply_managed_webhook(_payload(group_id="2")) is True

    assert coordinator.data.alarm_groups["2"].armed is True
    assert coordinator.data.alarm_groups["3"].armed is False
    assert coordinator.data.alarm_groups["1"].armed is False
    assert coordinator.data.alarm_groups["2"].alarm_count == 3


def test_child_webhook_does_not_change_parent() -> None:
    coordinator = _coordinator(
        {
            "1": KentixAlarmGroup(
                id="1", name="Floor", parent_group_id="3", armed=False
            ),
            "2": KentixAlarmGroup(id="2", name="Site", armed=False),
            "3": KentixAlarmGroup(
                id="3", name="Building", parent_group_id="2", armed=False
            ),
        }
    )

    coordinator.async_apply_managed_webhook(_payload(group_id="3"))

    assert coordinator.data.alarm_groups["2"].armed is False
    assert coordinator.data.alarm_groups["3"].armed is True
    assert coordinator.data.alarm_groups["1"].armed is False


def test_older_webhook_cannot_overwrite_newer_state() -> None:
    coordinator = _coordinator(
        {"2": KentixAlarmGroup(id="2", name="Site", armed=False)}
    )
    coordinator.async_apply_managed_webhook(
        _payload(group_state="1", system_unixtime="200")
    )
    coordinator.async_apply_managed_webhook(
        _payload(group_state="0", system_unixtime="100")
    )
    assert coordinator.data.alarm_groups["2"].armed is True
