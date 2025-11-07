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
        'linux-x86_64-glibc',
        'linux-x86_64-musl',
        'darwin-x86_64',
        'darwin-aarch64'
    ]

    # Mapping from platform name to actual toolchain triplet
    PLATFORM_TO_TRIPLET = {
        'linux-x86_64-musl': 'x86_64-unknown-linux-musl',
        'linux-x86_64-glibc': 'x86_64-unknown-linux-gnu',
    }

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
        import os

        env = {
            'WORKDIR': workdir,
        }

        # Set PREFIXDIR based on platform
        if prefixdir:
            env['PREFIXDIR'] = prefixdir
        elif platform.startswith('linux'):
            # For Linux cross-compilation, use sysroot/usr/local
            if 'SYSROOT' in os.environ:
                env['PREFIXDIR'] = os.environ['SYSROOT'] + '/usr/local'
            else:
                env['PREFIXDIR'] = '/usr/local'
        elif platform.startswith('darwin-x86_64'):
            env['PREFIXDIR'] = '/usr/local'
        elif platform.startswith('darwin-aarch64'):
            env['PREFIXDIR'] = '/opt/homebrew'

        if 'SYSROOT' in os.environ:
            env['SYSROOT'] = os.environ['SYSROOT']

        # Ensure pkg-config can locate libraries installed into the prefix/sysroot
        pkg_config_paths = []
        prefix_path = env.get('PREFIXDIR')
        if prefix_path:
            for subdir in ('lib/pkgconfig', 'lib64/pkgconfig', 'share/pkgconfig', 'libdata/pkgconfig'):
                pkg_config_paths.append(os.path.join(prefix_path, subdir))

        sysroot_path = env.get('SYSROOT')
        if sysroot_path:
            for subdir in ('usr/lib/pkgconfig', 'usr/lib64/pkgconfig', 'usr/share/pkgconfig', 'usr/libdata/pkgconfig'):
                pkg_config_paths.append(os.path.join(sysroot_path, subdir))

        existing_pkg_config = os.environ.get('PKG_CONFIG_PATH')
        if existing_pkg_config:
            pkg_config_paths.append(existing_pkg_config)

        # Remove duplicates while preserving order
        seen_paths = set()
        ordered_paths = []
        for path in pkg_config_paths:
            if not path or path in seen_paths:
                continue
            seen_paths.add(path)
            ordered_paths.append(path)

        if ordered_paths:
            env['PKG_CONFIG_PATH'] = ':'.join(ordered_paths)

        # Add cross-compilation toolchain file paths
        meson_file = CrossCompilingToolchainManager.get_meson_cross_file(platform)
        if meson_file:
            env['MESON_CROSS_FILE'] = meson_file

        cmake_file = CrossCompilingToolchainManager.get_cmake_toolchain_file(platform)
        if cmake_file:
            env['CMAKE_TOOLCHAIN_FILE'] = cmake_file

        # Add target triplet for configure --host
        triplet = CrossCompilingToolchainManager.get_toolchain_triplet(platform)
        if triplet:
            env['TARGET_TRIPLET'] = triplet

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

    @staticmethod
    def load_toolchains_config(plugins_dir: str = 'plugins') -> Dict[str, Any]:
        """
        Load toolchain configuration from toolchains.yml.

        Args:
            plugins_dir: Directory containing plugin configs

        Returns:
            Parsed toolchain configuration or empty dict if not found
        """
        toolchains_path = Path(plugins_dir) / 'toolchains.yml'

        if not toolchains_path.exists():
            print(f"Warning: toolchains.yml not found at {toolchains_path}")
            return {}

        with open(toolchains_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)


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


class CrossCompilingToolchainManager:
    """
    Manage cross-compilation toolchains for different platforms.
    Provides methods to get toolchain paths, environment variables, and build commands.
    """

    # Default toolchain base path
    DEFAULT_TOOLCHAIN_PATH = os.path.expanduser('~/x-tools')
    _toolchain_config_cache = None

    @classmethod
    def _get_toolchain_config(cls) -> Dict[str, Any]:
        """
        Load and cache toolchain configuration from toolchains.yml.

        Returns:
            Toolchain configuration dict
        """
        if cls._toolchain_config_cache is None:
            plugins_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins')
            cls._toolchain_config_cache = YAMLLoader.load_toolchains_config(plugins_dir)
        return cls._toolchain_config_cache.get('toolchains', {})

    @classmethod
    def get_toolchain_config(cls, platform: str) -> Optional[Dict[str, Any]]:
        """
        Get toolchain configuration for a specific platform.

        Args:
            platform: Platform name (e.g., 'linux-x86_64-musl')

        Returns:
            Toolchain configuration dict or None
        """
        toolchain_config = cls._get_toolchain_config()
        return toolchain_config.get(platform)

    @staticmethod
    def get_toolchain_triplet(platform: str) -> Optional[str]:
        """
        Get the actual toolchain triplet for a given platform.

        Args:
            platform: Platform name (e.g., 'linux-x86_64-musl')

        Returns:
            Toolchain triplet (e.g., 'x86_64-unknown-linux-musl') or None if not a cross-compilation platform
        """
        config = CrossCompilingToolchainManager.get_toolchain_config(platform)
        return config.get('triplet') if config else None

    @staticmethod
    def get_toolchain_bin_path(platform: str) -> Optional[str]:
        """
        Get the toolchain binary directory path for a platform.

        Args:
            platform: Platform name

        Returns:
            Path to toolchain bin directory or None
        """
        config = CrossCompilingToolchainManager.get_toolchain_config(platform)
        if not config:
            return None

        bin_path = config.get('bin_path')
        if bin_path:
            return os.path.expanduser(bin_path)

        return None

    @staticmethod
    def get_sysroot_path(platform: str) -> Optional[str]:
        """
        Get the sysroot path for a platform.

        Args:
            platform: Platform name

        Returns:
            Sysroot path or None
        """
        config = CrossCompilingToolchainManager.get_toolchain_config(platform)
        if not config:
            return None

        sysroot = config.get('sysroot')
        if sysroot:
            return os.path.expanduser(sysroot)

        return None

    @staticmethod
    def get_toolchain_env_vars(platform: str, static_linking: bool = True) -> Dict[str, str]:
        """
        Get environment variables for cross-compilation.

        Args:
            platform: Target platform
            static_linking: Whether to use static linking (default: True)

        Returns:
            Dictionary of environment variables
        """
        config = CrossCompilingToolchainManager.get_toolchain_config(platform)
        if not config:
            return {}

        env = {}
        binaries = config.get('binaries', {})

        # Set compiler and tool variables from config
        for key, value in binaries.items():
            env[key.upper()] = value

        # Add SYSROOT
        sysroot = CrossCompilingToolchainManager.get_sysroot_path(platform)
        if sysroot:
            env['SYSROOT'] = sysroot

        # Set flags with sysroot
        if sysroot:
            env['CFLAGS'] = f'--sysroot={sysroot}'
            env['CXXFLAGS'] = f'--sysroot={sysroot}'
            env['LDFLAGS'] = f'--sysroot={sysroot}'

        return env

    @staticmethod
    def get_meson_cross_file(platform: str, toolchains_dir: str = 'toolchains') -> Optional[str]:
        """
        Get the path to meson cross file for a platform.

        Args:
            platform: Platform name
            toolchains_dir: Directory containing toolchain config files

        Returns:
            Path to meson cross file or None
        """
        config = CrossCompilingToolchainManager.get_toolchain_config(platform)
        if not config:
            return None

        files = config.get('files', {})
        meson_file = files.get('meson')

        if meson_file:
            # Check if absolute path, if not, make it relative to project root
            if not os.path.isabs(meson_file):
                project_root = os.path.dirname(os.path.dirname(__file__))
                meson_file = os.path.join(project_root, meson_file)

            if os.path.exists(meson_file):
                return meson_file

        return None

    @staticmethod
    def get_cmake_toolchain_file(platform: str, toolchains_dir: str = 'toolchains') -> Optional[str]:
        """
        Get the path to cmake toolchain file for a platform.

        Args:
            platform: Platform name
            toolchains_dir: Directory containing toolchain config files

        Returns:
            Path to cmake toolchain file or None
        """
        config = CrossCompilingToolchainManager.get_toolchain_config(platform)
        if not config:
            return None

        files = config.get('files', {})
        cmake_file = files.get('cmake')

        if cmake_file:
            # Check if absolute path, if not, make it relative to project root
            if not os.path.isabs(cmake_file):
                project_root = os.path.dirname(os.path.dirname(__file__))
                cmake_file = os.path.join(project_root, cmake_file)

            if os.path.exists(cmake_file):
                return cmake_file

        return None

    @staticmethod
    def update_build_env(build_env: Dict[str, str], platform: str,
                        toolchains_dir: str = 'toolchains',
                        static_linking: bool = True) -> None:
        """
        Update build environment with cross-compilation toolchain variables.

        Args:
            build_env: Build environment dictionary to update
            platform: Target platform
            toolchains_dir: Directory containing toolchain config files
            static_linking: Whether to use static linking
        """
        toolchain_env = CrossCompilingToolchainManager.get_toolchain_env_vars(
            platform, static_linking)

        for key, value in toolchain_env.items():
            if key in build_env:
                # Append if already exists
                if value and build_env[key]:
                    build_env[key] = f"{build_env[key]} {value}"
            else:
                build_env[key] = value

        # Add toolchain bin to PATH
        bin_path = CrossCompilingToolchainManager.get_toolchain_bin_path(platform)
        if bin_path:
            if 'PATH' in build_env:
                build_env['PATH'] = f"{bin_path}:{build_env['PATH']}"
            else:
                build_env['PATH'] = bin_path


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
    for pattern in ['linux-.*', 'darwin-.*', '(linux|darwin)-.*']:
        print(f"\nPattern: {pattern}")
        matches = PlatformMatcher.get_matching_platforms(pattern)
        print(f"Matches: {matches}")
