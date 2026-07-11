"""Regression tests for user-facing release settings."""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _constant_value(name: str):
    tree = ast.parse((ROOT / "custom_components/kentix/const.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Constant {name} not found")


def test_default_polling_interval_is_60_seconds() -> None:
    assert _constant_value("DEFAULT_SCAN_INTERVAL") == 60


def test_polling_range_remains_configurable() -> None:
    assert _constant_value("MIN_SCAN_INTERVAL") == 5
    assert _constant_value("MAX_SCAN_INTERVAL") == 3600


def test_german_polling_guidance_is_present() -> None:
    payload = json.loads(
        (ROOT / "custom_components/kentix/translations/de.json").read_text()
    )
    description = payload["options"]["step"]["init"]["data_description"][
        "scan_interval"
    ]
    assert "Standard: 60 Sekunden" in description
    assert "ältere Kentix-Hardware" in description
    assert "30 Sekunden" in description


def test_tls_verification_is_disabled_by_default() -> None:
    assert _constant_value("DEFAULT_VERIFY_SSL") is False


def test_brand_assets_are_in_hacs_and_integration_directories() -> None:
    for relative in (
        "brand/icon.png",
        "custom_components/kentix/brand/icon.png",
        "custom_components/kentix/brand/logo.png",
        "assets/kentix-homeassistant.png",
    ):
        assert (ROOT / relative).is_file(), relative
