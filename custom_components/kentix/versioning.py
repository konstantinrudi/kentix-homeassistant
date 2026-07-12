"""KentixONE and SmartAPI version detection helpers."""

from __future__ import annotations

import re
from collections.abc import Mapping

from .models import KentixRuntimeDevice

_VERSION_RE = re.compile(r"^0*(\d+)\.0*(\d+)(?:\.0*(\d+))?(.*)$")
_CONTROLLER_TYPES = (101, 100, 102, 103)


def normalize_kentix_version(value: str | None) -> str | None:
    """Normalize values such as ``08.06.02 B01579`` for display."""
    if not value:
        return None
    text = value.strip()
    match = _VERSION_RE.match(text)
    if match is None:
        return text
    major, minor, patch, suffix = match.groups()
    normalized = f"{int(major)}.{int(minor)}"
    if patch is not None:
        normalized += f".{int(patch)}"
    return normalized + suffix


def detect_kentixone_version(
    devices: Mapping[str, KentixRuntimeDevice],
) -> str | None:
    """Return the most likely KentixONE controller software version."""
    for type_code in _CONTROLLER_TYPES:
        for device in devices.values():
            if device.type_code == type_code and device.version:
                return normalize_kentix_version(device.version)
    for device in devices.values():
        if device.version and _VERSION_RE.match(device.version.strip()):
            return normalize_kentix_version(device.version)
    return None


def detect_smartapi_version(
    devices: Mapping[str, KentixRuntimeDevice],
) -> str | None:
    """Derive the SmartAPI compatibility profile from KentixONE major/minor."""
    version = detect_kentixone_version(devices)
    if version is None:
        return None
    match = re.match(r"^(\d+)\.(\d+)", version)
    if match is None:
        return None
    return f"{match.group(1)}.{match.group(2)}"
