"""Reliability and maintenance-action regression tests."""

from custom_components.kentix.const import UNAVAILABLE_AFTER_FAILURES


def test_unavailable_threshold_is_three_failures() -> None:
    assert UNAVAILABLE_AFTER_FAILURES == 3


def test_maintenance_buttons_are_translated() -> None:
    import json
    from pathlib import Path

    data = json.loads(Path("custom_components/kentix/translations/de.json").read_text())
    buttons = data["entity"]["button"]
    assert "repair_webhook" in buttons
    assert "refresh_states" in buttons
    assert "rediscover_devices" in buttons
