"""Regression coverage for Home Assistant webhook imports."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_local_webhook_handler_does_not_shadow_home_assistant_component() -> None:
    code = """
import custom_components.kentix as integration
assert integration.ha_webhook.__name__ == 'homeassistant.components.webhook'
assert hasattr(integration.ha_webhook, 'async_generate_id')
assert hasattr(integration.ha_webhook, 'async_generate_url')
assert hasattr(integration.ha_webhook, 'async_generate_path')
"""
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_shadowing_webhook_module_no_longer_exists() -> None:
    integration_dir = ROOT / "custom_components" / "kentix"
    assert not (integration_dir / "webhook.py").exists()
    assert (integration_dir / "webhook_handler.py").is_file()
