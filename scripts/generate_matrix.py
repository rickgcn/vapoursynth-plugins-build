#!/usr/bin/env python3
"""
Generate build matrix for GitHub Actions.
Creates a matrix of (plugin, version, platform) combinations based on
plugin YAML configurations.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils import YAMLLoader, PlatformMatcher, BuildConfigResolver


def generate_build_matrix(
    plugins: List[str],
    plugins_dir: str = 'plugins'
) -> List[Dict[str, str]]:
    """
    Generate build matrix entries for specified plugins.

    Args:
        plugins: List of plugin names to build (empty = all plugins)
        plugins_dir: Directory containing plugin configurations

    Returns:
        List of matrix entries with 'plugin', 'version', and 'platform' keys
    """
    matrix_entries = []

    # Get all plugins if none specified
    if not plugins:
        plugins = YAMLLoader.get_all_plugins(plugins_dir)

    print(f"Generating build matrix for {len(plugins)} plugin(s)...", file=sys.stderr)

    for plugin_name in plugins:
        try:
            config = YAMLLoader.load_plugin_config(plugin_name, plugins_dir)
        except FileNotFoundError as e:
            print(f"Warning: {e}", file=sys.stderr)
            continue

        # Process each release version
        releases = config.get('releases', [])
        for release in releases:
            version = release['version']
            build_config = release.get('build', {})

            # Find all platforms supported by this release
            supported_platforms = set()
            for pattern in build_config.keys():
                matching = PlatformMatcher.get_matching_platforms(pattern)
                supported_platforms.update(matching)

            # Create matrix entry for each supported platform
            for platform in sorted(supported_platforms):
                matrix_entries.append({
                    'plugin': plugin_name,
                    'version': version,
                    'platform': platform
                })

    print(f"Generated {len(matrix_entries)} matrix entries", file=sys.stderr)
    return matrix_entries


def generate_test_matrix(
    plugins: List[str],
    plugins_dir: str = 'plugins'
) -> List[Dict[str, Any]]:
    """
    Generate test matrix entries for specified plugins.

    Args:
        plugins: List of plugin names to test (empty = all plugins)
        plugins_dir: Directory containing plugin configurations

    Returns:
        List of test matrix entries with plugin, version, platform, and test info
    """
    matrix_entries = []

    # Get all plugins if none specified
    if not plugins:
        plugins = YAMLLoader.get_all_plugins(plugins_dir)

    print(f"Generating test matrix for {len(plugins)} plugin(s)...", file=sys.stderr)

    for plugin_name in plugins:
        try:
            config = YAMLLoader.load_plugin_config(plugin_name, plugins_dir)
        except FileNotFoundError as e:
            print(f"Warning: {e}", file=sys.stderr)
            continue

        # Get tests if any
        tests = config.get('tests', [])
        if not tests:
            continue

        # Process each release version
        releases = config.get('releases', [])
        for release in releases:
            version = release['version']
            build_config = release.get('build', {})

            # Find all platforms supported by this release
            supported_platforms = set()
            for pattern in build_config.keys():
                matching = PlatformMatcher.get_matching_platforms(pattern)
                supported_platforms.update(matching)

            # Create test matrix entry for each (plugin, version, platform, test)
            for platform in sorted(supported_platforms):
                for test in tests:
                    test_name = test['name']
                    matrix_entries.append({
                        'plugin': plugin_name,
                        'version': version,
                        'platform': platform,
                        'test_name': test_name
                    })

    print(f"Generated {len(matrix_entries)} test matrix entries", file=sys.stderr)
    return matrix_entries


def get_runner_for_platform(platform: str) -> str:
    """
    Get GitHub Actions runner for a platform.

    Args:
        platform: Platform name

    Returns:
        GitHub Actions runner label
    """
    if platform.startswith('linux'):
        return 'ubuntu-24.04'
    elif platform.startswith('darwin'):
        if 'aarch64' in platform:
            return 'macos-15'  # Apple Silicon (M1/M2/M3)
        else:
            return 'macos-15-intel'  # Intel
    else:
        raise ValueError(f"Unknown platform: {platform}")


def add_runner_to_matrix(matrix_entries: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Add 'runner' field to each matrix entry.

    Args:
        matrix_entries: List of matrix entries

    Returns:
        Matrix entries with 'runner' field added
    """
    for entry in matrix_entries:
        entry['runner'] = get_runner_for_platform(entry['platform'])
    return matrix_entries


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate build/test matrix for VapourSynth plugins'
    )
    parser.add_argument(
        '--type',
        choices=['build', 'test'],
        required=True,
        help='Type of matrix to generate'
    )
    parser.add_argument(
        '--plugins',
        nargs='*',
        default=[],
        help='Plugin names (default: all plugins)'
    )
    parser.add_argument(
        '--plugins-dir',
        default='plugins',
        help='Directory containing plugin configs (default: plugins)'
    )
    parser.add_argument(
        '--output',
        default='json',
        choices=['json', 'github'],
        help='Output format (default: json)'
    )

    args = parser.parse_args()

    # Generate matrix based on type
    if args.type == 'build':
        matrix_entries = generate_build_matrix(args.plugins, args.plugins_dir)
    else:  # test
        matrix_entries = generate_test_matrix(args.plugins, args.plugins_dir)

    # Add runner information
    matrix_entries = add_runner_to_matrix(matrix_entries)

    # Output in requested format
    if args.output == 'json':
        print(json.dumps(matrix_entries, indent=2))
    elif args.output == 'github':
        # GitHub Actions matrix format
        matrix = {'include': matrix_entries}
        # Output in format that can be set as GitHub Actions output
        # Using the new format for multiline outputs
        print(json.dumps(matrix))


if __name__ == '__main__':
    main()
