"""Tests for optional runtime-device visibility."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.kentix.const import CONF_SHOW_ACCESS_MANAGERS
from custom_components.kentix.models import KentixRuntimeDevice
from custom_components.kentix.visibility import runtime_device_visible


def _entry(options=None):
    return SimpleNamespace(options=options or {})


def test_access_manager_is_hidden_by_default() -> None:
    device = KentixRuntimeDevice(id="10", name="AccessManager", type_code=105)
    assert runtime_device_visible(_entry(), device) is False


def test_access_manager_can_be_enabled_in_options() -> None:
    device = KentixRuntimeDevice(id="10", name="AccessManager", type_code=105)
    assert (
        runtime_device_visible(
            _entry({CONF_SHOW_ACCESS_MANAGERS: True}),
            device,
        )
        is True
    )


def test_doorlock_runtime_device_stays_hidden_because_it_has_dedicated_device() -> None:
    device = KentixRuntimeDevice(id="11", name="DoorLock", type_code=21)
    assert (
        runtime_device_visible(_entry({CONF_SHOW_ACCESS_MANAGERS: True}), device)
        is False
    )


def test_multisensor_remains_visible() -> None:
    device = KentixRuntimeDevice(id="4", name="MultiSensor", type_code=2)
    assert runtime_device_visible(_entry(), device) is True


def test_access_manager_controller_is_hidden_from_doorlock_relationship() -> None:
    from custom_components.kentix.models import KentixDoorLock

    locks = {"11": KentixDoorLock(id="11", name="Entrance", raw={"device_id": 116})}
    controller = KentixRuntimeDevice(id="116", name="Access controller", type_code=116)
    assert runtime_device_visible(_entry(), controller, locks) is False
    assert (
        runtime_device_visible(
            _entry({CONF_SHOW_ACCESS_MANAGERS: True}), controller, locks
        )
        is True
    )


def test_newer_doorlock_runtime_types_are_hidden() -> None:
    for type_code in (25, 26, 28):
        device = KentixRuntimeDevice(
            id=str(type_code), name=f"DoorLock {type_code}", type_code=type_code
        )
        assert runtime_device_visible(_entry(), device) is False
