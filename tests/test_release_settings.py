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


def test_default_polling_interval_is_five_minutes() -> None:
    assert _constant_value("DEFAULT_SCAN_INTERVAL") == 300


def test_automatic_webhook_management_is_enabled_by_default() -> None:
    assert _constant_value("DEFAULT_MANAGE_WEBHOOK") is True
    config_flow = (ROOT / "custom_components/kentix/config_flow.py").read_text()
    assert "CONF_MANAGE_WEBHOOK: DEFAULT_MANAGE_WEBHOOK" in config_flow


def test_access_managers_are_hidden_by_default_and_configurable() -> None:
    assert _constant_value("DEFAULT_SHOW_ACCESS_MANAGERS") is False
    config_flow = (ROOT / "custom_components/kentix/config_flow.py").read_text()
    assert "CONF_SHOW_ACCESS_MANAGERS" in config_flow
    translations = json.loads(
        (ROOT / "custom_components/kentix/translations/de.json").read_text()
    )
    assert (
        translations["options"]["step"]["init"]["data"]["show_access_managers"]
        == "AccessManager in Home Assistant anzeigen"
    )


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
    assert "Standard: 300 Sekunden" in description
    assert "Sicherheitsabgleichen" in description
    assert "MultiSensor-Werte" in description


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


def test_manifest_keys_follow_hassfest_order() -> None:
    manifest = json.loads((ROOT / "custom_components/kentix/manifest.json").read_text())
    keys = list(manifest)
    assert keys[:2] == ["domain", "name"]
    assert keys[2:] == sorted(keys[2:])


def test_repository_configuration_preserves_manifest_order() -> None:
    script = (ROOT / "scripts/configure_repository.py").read_text()
    assert "sort_keys=True" not in script
    assert '"domain",' in script
    assert '"name",' in script


def test_pytest_asyncio_mode_matches_home_assistant_core() -> None:
    """Home Assistant test fixtures require pytest-asyncio auto mode."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'asyncio_mode = "auto"' in pyproject
    assert 'asyncio_default_fixture_loop_scope = "function"' in pyproject


def test_release_version_is_0_4_4() -> None:
    manifest = json.loads((ROOT / "custom_components/kentix/manifest.json").read_text())
    assert manifest["version"] == "0.4.4"


def test_inventory_and_battery_refresh_are_limited_to_four_hours() -> None:
    const_source = (ROOT / "custom_components/kentix/const.py").read_text()
    assert "INVENTORY_REFRESH_INTERVAL = timedelta(hours=4)" in const_source

    coordinator_source = (ROOT / "custom_components/kentix/coordinator.py").read_text()
    assert (
        "now - self.last_inventory_refresh >= INVENTORY_REFRESH_INTERVAL"
        in coordinator_source
    )
    assert "self.client.async_get_system_values()" in coordinator_source


def test_periodic_detail_requests_are_removed() -> None:
    api_source = (ROOT / "custom_components/kentix/api.py").read_text()
    assert "alarm_group_details" not in api_source
    assert "door_lock_details" not in api_source
    assert "_enrich_sparse_items" not in api_source


def test_readme_documents_low_load_schedule_and_webhooks() -> None:
    readme = (ROOT / "README.md").read_text()
    assert "at most every **4 hours**" in readme
    assert "Automation → Webhooks" in readme
    assert "After every switching operation" in readme
    assert "Repository setup before publishing" not in readme
    assert "YOUR_GITHUB_USERNAME" not in readme
    assert "python scripts/configure_repository.py" not in readme
    assert "pytest" not in readme
    assert "release candidate" not in readme


def test_setup_python_uses_node_24_action() -> None:
    workflow = (ROOT / ".github/workflows/tests.yml").read_text()
    assert "actions/setup-python@v6" in workflow
    assert "actions/setup-python@v5" not in workflow


def test_doorlock_release_uses_put() -> None:
    api_source = (ROOT / "custom_components/kentix/api.py").read_text()
    assert '"PUT", self._routes.door_lock_open' in api_source
    assert '"POST", self._routes.door_lock_open' not in api_source


def test_temporary_upgrade_documents_are_not_shipped() -> None:
    assert not list((ROOT / "docs").glob("UPGRADE_*.md"))


def test_readme_shows_project_artwork() -> None:
    readme = (ROOT / "README.md").read_text()
    assert 'src="assets/kentix-homeassistant.png"' in readme
    assert "PUT /api/doorlocks/{id}/open" in readme


def test_apache_license_and_attribution_are_present() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    manifest = json.loads(
        (ROOT / "custom_components/kentix/manifest.json").read_text(encoding="utf-8")
    )

    assert "Apache License" in license_text
    assert "Version 2.0, January 2004" in license_text
    assert "@konstantinrudi" in notice
    assert "Apache License 2.0" in readme
    assert manifest["codeowners"] == ["@konstantinrudi"]
    assert "OWNER" not in manifest["documentation"]
    assert "OWNER" not in manifest["issue_tracker"]


def test_door_battery_entity_is_created_before_first_value() -> None:
    """DoorLock battery entity must exist even if initial telemetry is absent."""
    sensor_source = (ROOT / "custom_components/kentix/sensor.py").read_text(
        encoding="utf-8"
    )
    assert "KentixDoorBattery(coordinator, entry, door_lock)" in sensor_source
    assert "if door_lock.battery_level is not None:" not in sensor_source
    assert "KentixDoorSignalStrength(coordinator, entry, door_lock)" in sensor_source
