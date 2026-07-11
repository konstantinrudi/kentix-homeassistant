#!/usr/bin/env python3
"""Set repository-specific GitHub metadata before first publication."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "kentix" / "manifest.json"
OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")


def main() -> int:
    if len(sys.argv) != 2 or not OWNER_RE.fullmatch(sys.argv[1]):
        print("Usage: python scripts/configure_repository.py GITHUB_USERNAME")
        return 2

    owner = sys.argv[1]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["documentation"] = f"https://github.com/{owner}/kentix-homeassistant"
    manifest["issue_tracker"] = (
        f"https://github.com/{owner}/kentix-homeassistant/issues"
    )
    manifest["codeowners"] = [f"@{owner}"]
    preferred_order = (
        "domain",
        "name",
        "codeowners",
        "config_flow",
        "dependencies",
        "documentation",
        "integration_type",
        "iot_class",
        "issue_tracker",
        "requirements",
        "version",
    )
    ordered_manifest = {
        key: manifest[key] for key in preferred_order if key in manifest
    }
    ordered_manifest.update(
        {key: manifest[key] for key in sorted(set(manifest) - set(ordered_manifest))}
    )
    MANIFEST.write_text(
        json.dumps(ordered_manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Configured repository metadata for @{owner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
