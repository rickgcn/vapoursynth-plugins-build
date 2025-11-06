#!/usr/bin/env python3
"""Generate a test matrix restricted to platforms with successful builds."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


MatrixEntry = Dict[str, str]


def _load_json_file(path: Path) -> Sequence[MatrixEntry]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _collect_successful_builds(build_dir: Path) -> Iterable[Tuple[str, str, str]]:
    if not build_dir.exists():
        return []

    success = []
    for file_path in build_dir.rglob("*.json"):
        try:
            with file_path.open("r", encoding="utf-8") as fh:
                record = json.load(fh)
        except Exception as exc:  # pragma: no cover - diagnostic output only
            print(f"Warning: unable to parse {file_path}: {exc}")
            continue

        if record.get("status") == "success":
            success.append(
                (record["plugin"], record["version"], record["platform"])
            )
    return success


def write_outputs(matrix: List[MatrixEntry], output_path: Path) -> None:
    github_matrix = {"include": matrix}
    print("Filtered test matrix:")
    print(json.dumps(github_matrix, indent=2))

    with output_path.open("a", encoding="utf-8") as fh:
        fh.write(f"has-tests={'true' if matrix else 'false'}\n")
        fh.write("matrix=" + json.dumps(github_matrix) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-matrix", required=True, type=Path)
    parser.add_argument(
        "--build-results-dir", default="build-results", type=Path
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
    base_matrix = _load_json_file(args.base_matrix)
    success_keys = set(_collect_successful_builds(args.build_results_dir))
    print(f"Found {len(success_keys)} successful build entries")

    filtered = [
        entry
        for entry in base_matrix
        if (entry["plugin"], entry["version"], entry["platform"])
        in success_keys
    ]

    if not args.output:
        raise SystemExit("Output path is required (set --output or GITHUB_OUTPUT)")
    write_outputs(filtered, args.output)


if __name__ == "__main__":
    main()
