"""Naming and hierarchy helpers for Kentix objects."""

from __future__ import annotations

from collections.abc import Mapping

from .const import DOMAIN
from .models import KentixAlarmGroup, KentixDoorLock

_LEVEL_LABELS = {
    0: "Standort",
    1: "Gebäude",
    2: "Etage",
}


def alarm_group_depth(
    group: KentixAlarmGroup,
    groups: Mapping[str, KentixAlarmGroup],
) -> int:
    """Return the hierarchy depth of an alarm group without following cycles."""
    depth = 0
    current = group
    visited = {group.id}

    while current.parent_group_id is not None:
        parent_id = current.parent_group_id
        if parent_id in visited:
            break
        parent = groups.get(parent_id)
        if parent is None:
            break
        visited.add(parent_id)
        depth += 1
        current = parent

    return depth


def alarm_group_level_label(
    group: KentixAlarmGroup,
    groups: Mapping[str, KentixAlarmGroup],
) -> str:
    """Return the German Kentix hierarchy label used in Home Assistant."""
    depth = alarm_group_depth(group, groups)
    return _LEVEL_LABELS.get(depth, "Bereich")


def alarm_group_display_name(
    group: KentixAlarmGroup,
    groups: Mapping[str, KentixAlarmGroup],
) -> str:
    """Return a descriptive Home Assistant device name for an alarm group."""
    return f"{alarm_group_level_label(group, groups)} - {group.name}"


def alarm_group_parent_identifier(
    entry_id: str,
    group: KentixAlarmGroup,
    groups: Mapping[str, KentixAlarmGroup],
) -> tuple[str, str]:
    """Return the device identifier through which an alarm group is connected."""
    if group.parent_group_id in groups:
        return (DOMAIN, f"{entry_id}:alarm_group:{group.parent_group_id}")
    return (DOMAIN, entry_id)


def door_lock_parent_identifier(
    entry_id: str,
    door_lock: KentixDoorLock,
    groups: Mapping[str, KentixAlarmGroup],
) -> tuple[str, str]:
    """Return the parent alarm-group or hub identifier for a DoorLock."""
    if door_lock.parent_group_id in groups:
        return (DOMAIN, f"{entry_id}:alarm_group:{door_lock.parent_group_id}")
    return (DOMAIN, entry_id)
