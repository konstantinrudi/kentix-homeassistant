#!/usr/bin/env python3
"""Import every Kentix integration module against the installed Home Assistant."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODULES = (
    "custom_components.kentix",
    "custom_components.kentix.api",
    "custom_components.kentix.models",
    "custom_components.kentix.const",
    "custom_components.kentix.coordinator",
    "custom_components.kentix.webhook",
    "custom_components.kentix.config_flow",
    "custom_components.kentix.entity",
    "custom_components.kentix.discovery",
    "custom_components.kentix.alarm_control_panel",
    "custom_components.kentix.lock",
    "custom_components.kentix.button",
    "custom_components.kentix.binary_sensor",
    "custom_components.kentix.sensor",
    "custom_components.kentix.diagnostics",
)


def main() -> None:
    for module_name in MODULES:
        importlib.import_module(module_name)
    print(f"Imported {len(MODULES)} Kentix modules successfully")


if __name__ == "__main__":
    main()
