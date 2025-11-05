#!/usr/bin/env python3
"""
Utility functions for VapourSynth plugin build system.
Provides common functionality for parsing YAML configs, matching platforms,
and managing environment variables.
"""

import os
import re
import yaml
import hashlib
import urllib.request
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path


class PlatformMatcher:
    """Match platform patterns against actual platform names."""

    PLATFORMS = [
        'windows-x86',
        'windows-x64',
        'linux-x86_64-glibc',
        'linux-x86_64-musl',
        'darwin-x86_64',
        'darwin-aarch64'
    ]

    @staticmethod
    def match(pattern: str, platform: str) -> bool:
        """
        Check if a platform matches a pattern (regex).

        Args:
            pattern: Regex pattern from YAML config
            platform: Actual platform name

        Returns:
            True if platform matches pattern
        """
        try:
            return re.match(pattern, platform) is not None
        except re.error:
            return False

    @classmethod
    def get_matching_platforms(cls, pattern: str) -> List[str]:
        """
        Get all platforms that match a pattern.

        Args:
            pattern: Regex pattern from YAML config

        Returns:
            List of matching platform names
        """
        return [p for p in cls.PLATFORMS if cls.match(pattern, p)]


class EnvironmentManager:
    """Manage environment variables and path substitutions."""

    @staticmethod
    def get_default_env(platform: str, workdir: str, prefixdir: Optional[str] = None) -> Dict[str, str]:
        """
        Get default environment variables for a platform.

        Args:
            platform: Platform name (e.g., 'linux-x86_64-glibc')
            workdir: Working directory path
            prefixdir: Installation prefix directory (optional)

        Returns:
            Dictionary of environment variables
        """
        env = {
            'WORKDIR': workdir,
        }

        # Set PREFIXDIR based on platform
        if prefixdir:
            env['PREFIXDIR'] = prefixdir
        elif platform.startswith('linux') or platform.startswith('darwin-x86_64'):
            env['PREFIXDIR'] = '/usr/local'
        elif platform.startswith('darwin-aarch64'):
            env['PREFIXDIR'] = '/opt/homebrew'
        # Windows does not have PREFIXDIR

        return env

    @staticmethod
    def substitute_vars(text: str, env: Dict[str, str]) -> str:
        """
        Substitute environment variables in text.

        Args:
            text: Text containing {VAR} placeholders
            env: Dictionary of environment variables

        Returns:
            Text with variables substituted
        """
        result = text
        for key, value in env.items():
            result = result.replace(f"{{{key}}}", value)
        return result

    @staticmethod
    def merge_global_env(config_env: Dict, platform: str) -> Dict[str, str]:
        """
        Merge global env configurations based on platform matching.

        Args:
            config_env: Global env configuration from YAML config
            platform: Target platform (e.g., 'darwin-x86_64')

        Returns:
            Dictionary of merged environment variables
        """
        merged_env = {}

        # Iterate over env config and match patterns
        # Later patterns override earlier ones if they match
        for pattern, env_vars in config_env.items():
            if PlatformMatcher.match(pattern, platform):
                # Merge env_vars into merged_env (pattern matches later override earlier)
                for key, value in env_vars.items():
                    merged_env[key] = value

        return merged_env


class YAMLLoader:
    """Load and parse YAML plugin configuration files."""

    @staticmethod
    def load_plugin_config(plugin_name: str, plugins_dir: str = 'plugins') -> Dict[str, Any]:
        """
        Load plugin configuration from YAML file.

        Args:
            plugin_name: Name of the plugin
            plugins_dir: Directory containing plugin configs

        Returns:
            Parsed YAML configuration
        """
        config_path = Path(plugins_dir) / plugin_name / f"{plugin_name}.yml"

        if not config_path.exists():
            raise FileNotFoundError(f"Plugin config not found: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    @staticmethod
    def get_all_plugins(plugins_dir: str = 'plugins') -> List[str]:
        """
        Get list of all available plugins.

        Args:
            plugins_dir: Directory containing plugin configs

        Returns:
            List of plugin names
        """
        plugins = []
        plugins_path = Path(plugins_dir)

        if not plugins_path.exists():
            return []

        for item in plugins_path.iterdir():
            if item.is_dir():
                config_file = item / f"{item.name}.yml"
                if config_file.exists():
                    plugins.append(item.name)

        return sorted(plugins)


class FileDownloader:
    """Download and verify files."""

    @staticmethod
    def verify_hash(filepath: str, hash_str: str) -> bool:
        """
        Verify file hash.

        Args:
            filepath: Path to file
            hash_str: Hash string in format 'algorithm:hash'

        Returns:
            True if hash matches
        """
        algorithm, expected_hash = hash_str.split(':', 1)

        if algorithm == 'sha256sum':
            algorithm = 'sha256'

        hasher = hashlib.new(algorithm)

        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)

        actual_hash = hasher.hexdigest()
        return actual_hash == expected_hash

    @staticmethod
    def download_file(url: str, dest: str) -> None:
        """
        Download a file from URL.

        Args:
            url: Source URL
            dest: Destination file path
        """
        print(f"Downloading {url} to {dest}")

        dest_path = Path(dest)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        urllib.request.urlretrieve(url, dest)


class BuildConfigResolver:
    """Resolve build configuration for specific platform and version."""

    @staticmethod
    def get_build_config(config: Dict[str, Any], platform: str) -> Optional[Dict[str, Any]]:
        """
        Get build configuration for a specific platform.

        Args:
            config: Build section from YAML
            platform: Target platform

        Returns:
            Build configuration dict or None if no match
        """
        for pattern, build_config in config.items():
            if PlatformMatcher.match(pattern, platform):
                return build_config
        return None

    @staticmethod
    def get_artifacts(artifacts_config: Dict[str, Any], platform: str) -> List[str]:
        """
        Get artifact paths for a specific platform.

        Args:
            artifacts_config: Artifacts section from YAML
            platform: Target platform

        Returns:
            List of artifact paths
        """
        for pattern, artifact_list in artifacts_config.items():
            if PlatformMatcher.match(pattern, platform):
                return artifact_list
        return []

    @staticmethod
    def get_dependencies(deps_config: Dict[str, Any], platform: str) -> List[Dict[str, str]]:
        """
        Get dependencies for a specific platform.

        Args:
            deps_config: Dependencies section from YAML
            platform: Target platform

        Returns:
            List of dependency dicts with 'name' and 'version' keys
        """
        if not deps_config:
            return []

        for pattern, dep_list in deps_config.items():
            if PlatformMatcher.match(pattern, platform):
                return dep_list
        return []


def create_attachment_files(attachments: Dict[str, Any], env: Dict[str, str]) -> None:
    """
    Create attachment files from YAML configuration.

    Args:
        attachments: Attachments section from YAML
        env: Environment variables for path substitution
    """
    import base64
    import zstandard as zstd

    for filename, config in attachments.items():
        path = EnvironmentManager.substitute_vars(config['path'], env)
        encoding = config['encoding']
        data = config['data']

        # Create directory if needed
        Path(path).mkdir(parents=True, exist_ok=True)

        filepath = Path(path) / filename

        if encoding == 'text/utf-8':
            # Substitute variables in text content
            content = EnvironmentManager.substitute_vars(data, env)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        elif encoding == 'base64/zstd':
            # Decode base64 and decompress zstd
            compressed = base64.b64decode(data)
            decompressed = zstd.decompress(compressed)
            with open(filepath, 'wb') as f:
                f.write(decompressed)
        else:
            raise ValueError(f"Unsupported encoding: {encoding}")

        print(f"Created attachment: {filepath}")


if __name__ == '__main__':
    # Test platform matching
    print("Testing platform matching...")
    for pattern in ['windows-.*', 'linux-.*', 'darwin-.*', '(linux|darwin)-.*']:
        print(f"\nPattern: {pattern}")
        matches = PlatformMatcher.get_matching_platforms(pattern)
        print(f"Matches: {matches}")
