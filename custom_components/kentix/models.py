"""Data models and defensive SmartAPI response normalization."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

_CAMEL_RE_1 = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_RE_2 = re.compile(r"([a-z0-9])([A-Z])")


def _snake_case(value: str) -> str:
    """Convert a camelCase/PascalCase key to snake_case."""
    value = _CAMEL_RE_1.sub(r"\1_\2", value)
    return _CAMEL_RE_2.sub(r"\1_\2", value).lower().replace("-", "_")


def _normalized_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Add snake_case aliases and merge common nested state objects."""
    result: dict[str, Any] = {}
    for key, value in payload.items():
        text_key = str(key)
        result[text_key] = value
        result.setdefault(_snake_case(text_key), value)

    for nested_key in ("data", "details", "runtime", "values", "states"):
        nested = result.get(nested_key)
        if isinstance(nested, Mapping):
            for key, value in _normalized_payload(nested).items():
                result.setdefault(key, value)

    status = result.get("status")
    if isinstance(status, Mapping):
        for key, value in _normalized_payload(status).items():
            result.setdefault(key, value)
        result.pop("status", None)
    return result


def _first(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    """Return the first existing non-null value for a list of keys."""
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def _as_bool(value: Any) -> bool | None:
    """Convert common SmartAPI boolean representations."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower().replace("_", "-")
        if normalized in {
            "1",
            "true",
            "yes",
            "on",
            "open",
            "opened",
            "armed",
            "active",
            "alarm",
            "triggered",
            "locked",
            "online",
            "reachable",
        }:
            return True
        if normalized in {
            "0",
            "false",
            "no",
            "off",
            "closed",
            "disarmed",
            "inactive",
            "normal",
            "unlocked",
            "offline",
            "unreachable",
        }:
            return False
    return None


def _as_int(value: Any) -> int | None:
    """Convert a numeric API value to an integer."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(float(str(value).strip().rstrip("%")))
    except (TypeError, ValueError):
        return None


def _as_battery_percent(value: Any) -> int | None:
    """Convert numeric or categorical Kentix battery values to percent."""
    numeric = _as_int(value)
    if numeric is not None:
        return max(0, min(100, numeric))
    if not isinstance(value, str):
        return None
    category = value.strip().lower().replace("_", "-")
    return {
        "full": 100,
        "high": 75,
        "good": 75,
        "medium": 50,
        "normal": 50,
        "low": 25,
        "critical": 10,
        "empty": 0,
    }.get(category)


def _as_float(value: Any) -> float | None:
    """Convert a numeric API value to a float."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return None


def _as_id(value: Any) -> str:
    """Normalize an API identifier to a stable string."""
    if value is None:
        raise ValueError("Kentix object has no identifier")
    return str(value)


def _status_text(raw: Mapping[str, Any]) -> str | None:
    value = _first(
        raw,
        "switching_status",
        "switch_status",
        "arming_status",
        "alarm_state",
        "lock_state",
        "door_state",
        "state",
        "status",
    )
    if value is None:
        return None
    return str(value).strip().lower().replace("_", "-").replace(" ", "-")


@dataclass(frozen=True, slots=True)
class KentixAlarmGroup:
    """Normalized Kentix alarm group."""

    id: str
    name: str
    parent_group_id: str | None = None
    arm_delay: int | None = None
    has_prealarm: bool | None = None
    maintenance: str | None = None
    armed: bool | None = None
    partially_armed: bool = False
    arming: bool = False
    disarming: bool = False
    triggered: bool = False
    alarm_count: int | None = None
    warning_count: int | None = None
    raw_state: str | None = None
    last_changed_by: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> KentixAlarmGroup:
        """Create a normalized alarm group from Kentix JSON."""
        source = _normalized_payload(payload)
        object_id = _as_id(
            _first(source, "id", "alarmgroup_id", "alarm_group_id", "group_id")
        )
        name = str(
            _first(
                source,
                "name",
                "alarmgroup_name",
                "alarm_group_name",
                default=object_id,
            )
        )
        status = _status_text(source)

        armed = _as_bool(
            _first(
                source,
                "armed",
                "is_armed",
                "armed_state",
                "switch_state",
                "switching_state",
            )
        )
        if armed is None and status:
            if status in {
                "armed",
                "arm",
                "on",
                "active",
                "armed-away",
                "fully-armed",
            }:
                armed = True
            elif status in {"disarmed", "disarm", "off", "inactive", "unarmed"}:
                armed = False
        if status is None and armed is not None:
            status = "armed" if armed else "disarmed"

        partially_armed = bool(
            _as_bool(
                _first(
                    source,
                    "partially_armed",
                    "partial_armed",
                    "is_partially_armed",
                )
            )
            or status
            in {
                "partially-armed",
                "partial-armed",
                "part-armed",
                "armed-partial",
                "partiallyarmed",
            }
        )
        arming = bool(
            _as_bool(_first(source, "arming", "is_arming"))
            or status in {"arming", "arm-pending", "pending-arm"}
        )
        disarming = bool(
            _as_bool(_first(source, "disarming", "is_disarming"))
            or status in {"disarming", "disarm-pending", "pending-disarm"}
        )
        triggered = bool(
            _as_bool(
                _first(
                    source,
                    "triggered",
                    "alarm",
                    "alarm_active",
                    "active_alarm",
                    "has_alarm",
                )
            )
            or status in {"alarm", "triggered", "fire", "sabotage"}
        )

        alarm_count = _as_int(
            _first(
                source,
                "alarm_count",
                "active_alarm_count",
                "alarms",
                "pending_alarms",
            )
        )
        warning_count = _as_int(
            _first(
                source,
                "warning_count",
                "active_warning_count",
                "warnings",
                "pending_warnings",
            )
        )
        if alarm_count is not None and alarm_count > 0:
            triggered = True

        last_changed_by = _first(
            source,
            "changed_by",
            "last_changed_by",
            "switch_user",
            "user_name",
            "username",
        )

        parent_group = _first(source, "group_id", "parent_group_id")
        arm_delay = _as_int(_first(source, "arm_delay"))
        has_prealarm = _as_bool(_first(source, "has_prealarm"))
        maintenance = _first(source, "maintenance")

        return cls(
            id=object_id,
            name=name,
            parent_group_id=str(parent_group) if parent_group is not None else None,
            arm_delay=arm_delay,
            has_prealarm=has_prealarm,
            maintenance=str(maintenance) if maintenance is not None else None,
            armed=armed,
            partially_armed=partially_armed,
            arming=arming,
            disarming=disarming,
            triggered=triggered,
            alarm_count=alarm_count,
            warning_count=warning_count,
            raw_state=status,
            last_changed_by=str(last_changed_by) if last_changed_by else None,
            raw=dict(payload),
        )

    @property
    def event_state(self) -> str:
        """Return a stable state string for Home Assistant events."""
        if self.triggered:
            return "triggered"
        if self.arming:
            return "arming"
        if self.disarming:
            return "disarming"
        if self.partially_armed:
            return "partially_armed"
        if self.armed is True:
            return "armed"
        if self.armed is False:
            return "disarmed"
        return self.raw_state or "unknown"


@dataclass(frozen=True, slots=True)
class KentixDoorLock:
    """Normalized Kentix DoorLock."""

    id: str
    name: str
    parent_group_id: str | None = None
    arm_group_id: str | None = None
    enabled: bool | None = None
    has_door_contact: bool | None = None
    is_locked: bool | None = None
    is_open: bool | None = None
    is_jammed: bool = False
    available: bool | None = None
    battery_level: int | None = None
    signal_strength: float | None = None
    raw_state: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> KentixDoorLock:
        """Create a normalized DoorLock from Kentix JSON."""
        source = _normalized_payload(payload)
        object_id = _as_id(
            _first(source, "id", "doorlock_id", "door_lock_id", "device_id")
        )
        name = str(
            _first(
                source,
                "name",
                "doorlock_name",
                "door_lock_name",
                "device_name",
                default=object_id,
            )
        )
        status = _status_text(source)

        is_open = _as_bool(
            _first(
                source,
                "open",
                "is_open",
                "door_open",
                "reed_open",
                "door_contact",
                "contact_open",
            )
        )
        is_locked = _as_bool(
            _first(
                source,
                "locked",
                "is_locked",
                "bolt_locked",
                "lock_active",
                "engaged",
            )
        )

        if status:
            if status in {"open", "opened", "opening"}:
                is_open = True
            elif (
                status in {"closed", "locked", "unlocked", "ready"} and is_open is None
            ):
                is_open = False
            if status in {"locked", "engaged"}:
                is_locked = True
            elif status in {"unlocked", "open", "opened", "opening", "released"}:
                is_locked = False

        is_jammed = bool(
            _as_bool(_first(source, "jammed", "is_jammed", "blocked"))
            or status in {"jammed", "blocked", "error"}
        )
        # Only explicit runtime fields may be interpreted as reachability.
        # Kentix detail payloads contain connection alarm *configuration* but
        # do not necessarily contain the current connection state.
        available = _as_bool(
            _first(source, "available", "online", "reachable", "connected")
        )
        battery_level = _as_battery_percent(
            _first(
                source,
                "battery_level",
                "batterylevel",
                "battery_percent",
                "battery_percentage",
                "battery",
                "battery_state",
            )
        )
        signal_strength = _as_float(
            _first(source, "signal_strength", "rssi", "radio_rssi")
        )

        parent_group = _first(source, "group_id", "parent_group_id")
        arm_group = _first(source, "arm_group_id", "armgroup_id")
        enabled = _as_bool(_first(source, "is_active", "enabled"))
        reed_source_id = _first(source, "reed_source_id", "door_contact_source_id")
        reed_assignment = _first(source, "reed_assignment")
        has_door_contact: bool | None = None
        if reed_source_id is not None:
            has_door_contact = True
        elif reed_assignment is not None:
            has_door_contact = str(reed_assignment).strip().lower() != "off"

        return cls(
            id=object_id,
            name=name,
            parent_group_id=str(parent_group) if parent_group is not None else None,
            arm_group_id=str(arm_group) if arm_group is not None else None,
            enabled=enabled,
            has_door_contact=has_door_contact,
            is_locked=is_locked,
            is_open=is_open,
            is_jammed=is_jammed,
            available=available,
            battery_level=battery_level,
            signal_strength=signal_strength,
            raw_state=status,
            raw=dict(payload),
        )

    @property
    def event_state(self) -> str:
        """Return a stable state string for Home Assistant events."""
        if self.is_jammed:
            return "jammed"
        if self.is_open is True:
            return "open"
        if self.is_locked is True:
            return "locked"
        if self.is_locked is False:
            return "unlocked"
        if self.is_open is False:
            return "closed"
        return self.raw_state or "unknown"


@dataclass(frozen=True, slots=True)
class KentixData:
    """Coordinator snapshot."""

    alarm_groups: Mapping[str, KentixAlarmGroup]
    door_locks: Mapping[str, KentixDoorLock]
    alarm_groups_available: bool = True
    door_locks_available: bool = True
