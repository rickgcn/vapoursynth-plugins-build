#!/usr/bin/env python3
"""Record the outcome of a single test invocation."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


def _get_env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None or value == "":
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def _default_result_file() -> Path:
    plugin = _get_env("PLUGIN")
    version = _get_env("VERSION")
    platform = _get_env("PLATFORM")
    test_name = _get_env("TEST_NAME")
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", test_name)
    return Path("test-status") / f"{plugin}-{version}-{platform}-{slug}.json"


def main() -> None:
    result_file = Path(os.environ.get("RESULT_FILE") or _default_result_file())
    result_path_file = os.environ.get("RESULT_PATH_FILE")
    payload = {
        "plugin": _get_env("PLUGIN"),
        "version": _get_env("VERSION"),
        "platform": _get_env("PLATFORM"),
        "test_name": _get_env("TEST_NAME"),
        "runner": _get_env("RUNNER"),
        "status": os.environ.get("TEST_STATUS", ""),
    }

    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_text(json.dumps(payload), encoding="utf-8")
    print("Recorded test result:", json.dumps(payload))
    print(f"Result written to: {result_file}")

    if result_path_file:
        path_marker = Path(result_path_file)
        path_marker.parent.mkdir(parents=True, exist_ok=True)
        path_marker.write_text(str(result_file), encoding="utf-8")


if __name__ == "__main__":
    main()
