#!/usr/bin/env python3
"""Generate the release matrix by combining build/test metadata."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


Record = Dict[str, str]
Key = Tuple[str, str, str]


def _load_records(directory: Path) -> List[Record]:
    if not directory.exists():
        return []
    records: List[Record] = []
    for file_path in directory.rglob("*.json"):
        try:
            with file_path.open("r", encoding="utf-8") as fh:
                records.append(json.load(fh))
        except Exception as exc:  # pragma: no cover - best-effort logging only
            print(f"Warning: unable to parse {file_path}: {exc}")
    return records


def _load_base_test_matrix(path: Path) -> Sequence[Record]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build-results-dir",
        default=Path("release-info/build-results"),
        type=Path,
    )
    parser.add_argument(
        "--test-results-dir",
        default=Path("release-info/test-results"),
        type=Path,
    )
    parser.add_argument(
        "--base-test-matrix",
        default=Path("base_test_matrix.json"),
        type=Path,
    )
    parser.add_argument(
        "--output",
        default=Path(os.environ.get("GITHUB_OUTPUT", "")),
        type=Path,
        help="Path to the GitHub output file (default: $GITHUB_OUTPUT)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.output:
        raise SystemExit("Output path is required (set --output or GITHUB_OUTPUT)")

    build_records = _load_records(args.build_results_dir)
    test_records = _load_records(args.test_results_dir)
    base_test_entries = _load_base_test_matrix(args.base_test_matrix)

    build_status: Dict[Key, str] = {
        (record["plugin"], record["version"], record["platform"]): record.get("status", "")
        for record in build_records
    }

    tests_by_key: Dict[Key, List[Record]] = {}
    for record in test_records:
        key = (record["plugin"], record["version"], record["platform"])
        tests_by_key.setdefault(key, []).append(record)

    test_required_keys = {
        (entry["plugin"], entry["version"], entry["platform"])
        for entry in base_test_entries
    }

    test_pass_keys = {
        key
        for key, entries in tests_by_key.items()
        if entries and all(item.get("status") == "success" for item in entries)
    }

    release_candidates: List[Dict[str, str]] = []
    skipped_due_to_tests: List[Key] = []

    for key, status in build_status.items():
        if status != "success":
            continue
        requires_tests = key in test_required_keys
        if requires_tests and key not in test_pass_keys:
            skipped_due_to_tests.append(key)
            continue
        plugin, version, platform = key
        release_candidates.append(
            {"plugin": plugin, "version": version, "platform": platform}
        )

    if skipped_due_to_tests:
        print("Skipping release for the following platform(s) due to missing/failed tests:")
        for plugin, version, platform in sorted(skipped_due_to_tests):
            print(f"  - {plugin} {version} ({platform})")

    matrix_entries = sorted(
        release_candidates,
        key=lambda entry: (entry["plugin"], entry["version"], entry["platform"]),
    )

    github_matrix = {"include": matrix_entries}
    print("Release matrix candidates:")
    print(json.dumps(github_matrix, indent=2))

    with args.output.open("a", encoding="utf-8") as fh:
        fh.write(f"has-releases={'true' if matrix_entries else 'false'}\n")
        fh.write("matrix=" + json.dumps(github_matrix) + "\n")


if __name__ == "__main__":
    main()
