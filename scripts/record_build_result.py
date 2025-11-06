#!/usr/bin/env python3
"""Record the outcome of a build matrix entry for later workflow stages."""

from __future__ import annotations

import json
import os
from pathlib import Path


def _get_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    data = {
        "plugin": _get_env("PLUGIN"),
        "version": _get_env("VERSION"),
        "platform": _get_env("PLATFORM"),
        "runner": _get_env("RUNNER"),
        "status": _get_env("BUILD_STATUS"),
    }
    output_path = Path(_get_env("RESULT_FILE"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data), encoding="utf-8")
    print("Recorded build result:", json.dumps(data))


if __name__ == "__main__":
    main()
