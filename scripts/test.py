#!/usr/bin/env python3
"""
Test script for VapourSynth plugins.
Handles setting up test environment, creating attachments, and running tests
based on YAML configuration files.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    YAMLLoader,
    EnvironmentManager,
    create_attachment_files
)


class PluginTester:
    """Test VapourSynth plugins."""

    def __init__(
        self,
        plugin_name: str,
        version: str,
        platform: str,
        test_name: str,
        plugin_path: str,
        testdir: str,
        plugins_dir: str = 'plugins'
    ):
        """
        Initialize plugin tester.

        Args:
            plugin_name: Plugin name
            version: Plugin version
            platform: Target platform
            test_name: Name of test to run
            plugin_path: Path to plugin file
            testdir: Test working directory
            plugins_dir: Directory containing plugin configs
        """
        self.plugin_name = plugin_name
        self.version = version
        self.platform = platform
        self.test_name = test_name
        self.plugin_path = plugin_path
        self.testdir = Path(testdir)
        self.plugins_dir = plugins_dir

        # Create test directory
        self.testdir.mkdir(parents=True, exist_ok=True)

        # Setup environment variables
        self.env = {
            'TESTDIR': str(self.testdir),
            'PLUGIN_PATH': plugin_path
        }

        # Load plugin configuration
        self.config = YAMLLoader.load_plugin_config(plugin_name, plugins_dir)

        # Find the test configuration
        self.test_config = None
        for test in self.config.get('tests', []):
            if test['name'] == test_name:
                self.test_config = test
                break

        if not self.test_config:
            raise ValueError(f"Test '{test_name}' not found for plugin {plugin_name}")

    def run_test(self) -> bool:
        """
        Run the test.

        Returns:
            True if test passed, False otherwise
        """
        print(f"\n{'='*60}")
        print(f"Running test: {self.test_name}")
        print(f"Plugin: {self.plugin_name} {self.version} ({self.platform})")
        print(f"{'='*60}\n")

        # Create test attachments
        self._create_attachments()

        # Run test commands
        success = self._run_test_commands()

        if success:
            print(f"\n{'='*60}")
            print(f"Test PASSED: {self.test_name}")
            print(f"{'='*60}\n")
        else:
            print(f"\n{'='*60}")
            print(f"Test FAILED: {self.test_name}")
            print(f"{'='*60}\n")

        return success

    def _create_attachments(self) -> None:
        """Create test attachment files."""
        attachment_names = self.test_config.get('attachments', [])
        if not attachment_names:
            print("No attachments to create")
            return

        print(f"Creating {len(attachment_names)} attachment(s)...\n")

        # Get attachment configurations
        attachments_config = self.config.get('attachments', {})

        # Filter to only the attachments needed for this test
        test_attachments = {
            name: config
            for name, config in attachments_config.items()
            if name in attachment_names
        }

        if len(test_attachments) != len(attachment_names):
            missing = set(attachment_names) - set(test_attachments.keys())
            raise ValueError(f"Missing attachment configurations: {missing}")

        # Create the attachment files
        create_attachment_files(test_attachments, self.env)

    def _run_test_commands(self) -> bool:
        """
        Run test commands.

        Returns:
            True if all commands succeeded, False otherwise
        """
        commands = self.test_config.get('commands', [])
        if not commands:
            print("Warning: No test commands defined")
            return True

        print(f"\nRunning {len(commands)} test command(s)...\n")

        for cmd_entry in commands:
            if isinstance(cmd_entry, dict):
                cwd = cmd_entry.get('cwd', str(self.testdir))
                cmd = cmd_entry['cmd']
            else:
                cwd = str(self.testdir)
                cmd = cmd_entry

            # Substitute variables in command and cwd
            cmd = EnvironmentManager.substitute_vars(cmd, self.env)
            cwd = EnvironmentManager.substitute_vars(cwd, self.env)

            print(f"[{cwd}]$ {cmd}")

            # Execute command
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=cwd,
                    text=True,
                    capture_output=True
                )

                # Print output
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr, file=sys.stderr)

                if result.returncode != 0:
                    print(f"Command failed with exit code {result.returncode}")
                    return False

            except Exception as e:
                print(f"Command failed with exception: {e}")
                return False

        return True


def get_plugin_path_for_platform(platform: str, artifact_dir: str) -> str:
    """
    Get the expected plugin path for a platform.

    Args:
        platform: Platform name
        artifact_dir: Directory containing artifacts

    Returns:
        Path to plugin file
    """
    artifact_path = Path(artifact_dir)

    # Look for common plugin file patterns
    if platform.startswith('windows'):
        # Windows: .dll files
        dll_files = list(artifact_path.glob('*.dll'))
        if dll_files:
            return str(dll_files[0])
    elif platform.startswith('linux'):
        # Linux: .so files
        so_files = list(artifact_path.glob('*.so'))
        if so_files:
            return str(so_files[0])
    elif platform.startswith('darwin'):
        # macOS: .dylib files
        dylib_files = list(artifact_path.glob('*.dylib'))
        if dylib_files:
            return str(dylib_files[0])

    raise FileNotFoundError(f"No plugin file found in {artifact_dir} for platform {platform}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Test VapourSynth plugin')
    parser.add_argument('--plugin', required=True, help='Plugin name')
    parser.add_argument('--version', required=True, help='Plugin version')
    parser.add_argument('--platform', required=True, help='Target platform')
    parser.add_argument('--test-name', required=True, help='Name of test to run')
    parser.add_argument(
        '--plugin-path',
        help='Path to plugin file (auto-detect if not specified)'
    )
    parser.add_argument(
        '--artifact-dir',
        help='Directory containing artifacts (for auto-detection)'
    )
    parser.add_argument(
        '--testdir',
        required=True,
        help='Test working directory'
    )
    parser.add_argument(
        '--plugins-dir',
        default='plugins',
        help='Plugins directory'
    )

    args = parser.parse_args()

    # Determine plugin path
    if args.plugin_path:
        plugin_path = args.plugin_path
    elif args.artifact_dir:
        try:
            plugin_path = get_plugin_path_for_platform(args.platform, args.artifact_dir)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Error: Either --plugin-path or --artifact-dir must be specified", file=sys.stderr)
        sys.exit(1)

    # Verify plugin file exists
    if not Path(plugin_path).exists():
        print(f"Error: Plugin file not found: {plugin_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Using plugin: {plugin_path}")

    try:
        tester = PluginTester(
            plugin_name=args.plugin,
            version=args.version,
            platform=args.platform,
            test_name=args.test_name,
            plugin_path=plugin_path,
            testdir=args.testdir,
            plugins_dir=args.plugins_dir
        )

        success = tester.run_test()
        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
