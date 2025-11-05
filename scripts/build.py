#!/usr/bin/env python3
"""
Main build script for VapourSynth plugins.
Handles downloading sources, building dependencies, and building plugins
based on YAML configuration files.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    YAMLLoader,
    EnvironmentManager,
    FileDownloader,
    BuildConfigResolver,
    PlatformMatcher
)


class DependencyBuilder:
    """Build plugin dependencies."""

    def __init__(
        self,
        workdir: str,
        prefixdir: Optional[str],
        platform: str,
        nproc: int = 1,
        parent_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize dependency builder.

        Args:
            workdir: Working directory for builds
            prefixdir: Installation prefix directory
            platform: Target platform
            nproc: Number of parallel jobs
            parent_config: Parent plugin configuration (for global env)
        """
        self.workdir = Path(workdir)
        self.prefixdir = prefixdir
        self.platform = platform
        self.nproc = nproc
        self.env = EnvironmentManager.get_default_env(platform, str(workdir), prefixdir)
        # Add NPROC to environment
        self.env['NPROC'] = str(nproc)

        # Add parent's global env to self.env if provided
        if parent_config and 'env' in parent_config:
            global_env = EnvironmentManager.merge_global_env(parent_config['env'], platform)
            self.env.update(global_env)

    def build_dependency(
        self,
        dep_name: str,
        dep_version: str,
        dep_config: Dict[str, Any]
    ) -> None:
        """
        Build a single dependency.

        Args:
            dep_name: Dependency name
            dep_version: Version to build
            dep_config: Dependency configuration from YAML
        """
        print(f"\n{'='*60}")
        print(f"Building dependency: {dep_name} {dep_version}")
        print(f"{'='*60}\n")

        # Get version-specific config
        version_config = dep_config['versions'].get(dep_version)
        if not version_config:
            raise ValueError(f"Version {dep_version} not found for dependency {dep_name}")

        # Download source
        source_type = version_config['type']
        source_url = version_config['source']

        if source_type == 'tarball':
            filename = source_url.split('/')[-1]
            dest_path = self.workdir / filename

            if not dest_path.exists():
                FileDownloader.download_file(source_url, str(dest_path))

            # Verify hash if provided
            if 'hash' in version_config:
                print(f"Verifying hash for {filename}...")
                if not FileDownloader.verify_hash(str(dest_path), version_config['hash']):
                    raise ValueError(f"Hash verification failed for {filename}")
                print("Hash verification passed")

            # Add DL_FILE_NAME to environment
            self.env['DL_FILE_NAME'] = filename

        elif source_type == 'git':
            # Clone git repository
            repo_dir = self.workdir / dep_name
            if not repo_dir.exists():
                print(f"Cloning {source_url}...")
                subprocess.run(
                    ['git', 'clone', source_url, str(repo_dir)],
                    check=True
                )
                if 'tag' in version_config:
                    subprocess.run(
                        ['git', 'checkout', version_config['tag']],
                        cwd=str(repo_dir),
                        check=True
                    )
        else:
            raise ValueError(f"Unknown source type: {source_type}")

        # Get build configuration for this platform
        build_config = BuildConfigResolver.get_build_config(
            version_config['build'],
            self.platform
        )

        if not build_config:
            print(f"No build configuration for {self.platform}, skipping...")
            return

        # Execute build commands
        self._execute_build(build_config)

    def _execute_build(self, build_config: Dict[str, Any]) -> None:
        """
        Execute build commands.

        Args:
            build_config: Build configuration with env and commands
        """
        # Merge build environment with base environment
        build_env = os.environ.copy()

        # Add self.env variables first (includes DL_FILE_NAME, WORKDIR, etc.)
        for key, value in self.env.items():
            build_env[key] = value

        # Override with build_config env if specified
        if 'env' in build_config:
            for key, value in build_config['env'].items():
                # Substitute variables in environment values
                build_env[key] = EnvironmentManager.substitute_vars(value, self.env)

        # Execute commands
        commands = build_config.get('commands', [])
        current_cwd = str(self.workdir)  # Track current working directory

        for cmd_entry in commands:
            if isinstance(cmd_entry, dict):
                # Update cwd if specified, otherwise keep current
                if 'cwd' in cmd_entry:
                    current_cwd = cmd_entry['cwd']
                cmd = cmd_entry['cmd']
            else:
                cmd = cmd_entry

            # Substitute variables in command and cwd
            cmd = EnvironmentManager.substitute_vars(cmd, self.env)
            cwd = EnvironmentManager.substitute_vars(current_cwd, self.env)

            print(f"\n[{cwd}]$ {cmd}")

            # Execute command
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                env=build_env,
                text=True
            )

            if result.returncode != 0:
                raise RuntimeError(f"Command failed with exit code {result.returncode}")


class PluginBuilder:
    """Build VapourSynth plugins."""

    def __init__(
        self,
        plugin_name: str,
        version: str,
        platform: str,
        workdir: str,
        prefixdir: Optional[str] = None,
        plugins_dir: str = 'plugins',
        nproc: int = 1
    ):
        """
        Initialize plugin builder.

        Args:
            plugin_name: Plugin name
            version: Plugin version to build
            platform: Target platform
            workdir: Working directory
            prefixdir: Installation prefix directory
            plugins_dir: Directory containing plugin configs
            nproc: Number of parallel jobs
        """
        self.plugin_name = plugin_name
        self.version = version
        self.platform = platform
        self.workdir = Path(workdir)
        self.prefixdir = prefixdir
        self.plugins_dir = plugins_dir
        self.nproc = nproc

        self.workdir.mkdir(parents=True, exist_ok=True)

        self.env = EnvironmentManager.get_default_env(platform, str(workdir), prefixdir)
        # Add NPROC to environment
        self.env['NPROC'] = str(nproc)

        # Load plugin configuration
        self.config = YAMLLoader.load_plugin_config(plugin_name, plugins_dir)

        # Add global env to self.env if specified
        if 'env' in self.config:
            global_env = EnvironmentManager.merge_global_env(self.config['env'], platform)
            self.env.update(global_env)

        # Find the specific release
        self.release_config = None
        for release in self.config.get('releases', []):
            if release['version'] == version:
                self.release_config = release
                break

        if not self.release_config:
            raise ValueError(f"Version {version} not found for plugin {plugin_name}")

    def build(self) -> List[str]:
        """
        Build the plugin.

        Returns:
            List of artifact paths
        """
        print(f"\n{'='*60}")
        print(f"Building plugin: {self.plugin_name} {self.version} for {self.platform}")
        print(f"{'='*60}\n")

        # Build dependencies first
        self._build_dependencies()

        # Download plugin source
        self._download_source()

        # Build plugin
        self._build_plugin()

        # Collect artifacts
        artifacts = self._collect_artifacts()

        print(f"\n{'='*60}")
        print(f"Build completed successfully!")
        print(f"Artifacts: {artifacts}")
        print(f"{'='*60}\n")

        return artifacts

    def _build_dependencies(self) -> None:
        """Build plugin dependencies."""
        deps_config = self.release_config.get('dependencies', {})
        if not deps_config:
            print("No dependencies to build")
            return

        # Get dependencies for this platform
        dep_list = BuildConfigResolver.get_dependencies(deps_config, self.platform)
        if not dep_list:
            print(f"No dependencies for platform {self.platform}")
            return

        print(f"\nBuilding {len(dep_list)} dependencies...\n")

        # Get full dependency configurations
        full_deps_config = self.config.get('dependencies', {})

        # Build each dependency
        dep_builder = DependencyBuilder(
            str(self.workdir),
            self.prefixdir,
            self.platform,
            self.nproc,
            parent_config=self.config
        )
        for dep in dep_list:
            dep_name = dep['name']
            dep_version = dep['version']

            if dep_name not in full_deps_config:
                raise ValueError(f"Dependency {dep_name} not found in dependencies section")

            dep_builder.build_dependency(
                dep_name,
                dep_version,
                full_deps_config[dep_name]
            )

    def _download_source(self) -> None:
        """Download plugin source code."""
        source_type = self.release_config['type']
        source_url = self.release_config['source']

        if source_type == 'tarball':
            filename = source_url.split('/')[-1]
            dest_path = self.workdir / filename

            if not dest_path.exists():
                FileDownloader.download_file(source_url, str(dest_path))

            # Verify hash if provided
            if 'hash' in self.release_config:
                print(f"Verifying hash for {filename}...")
                if not FileDownloader.verify_hash(str(dest_path), self.release_config['hash']):
                    raise ValueError(f"Hash verification failed for {filename}")
                print("Hash verification passed")

            # Add DL_FILE_NAME to environment
            self.env['DL_FILE_NAME'] = filename

        elif source_type == 'git':
            # Clone git repository
            repo_dir = self.workdir / self.plugin_name
            if not repo_dir.exists():
                print(f"Cloning {source_url}...")
                subprocess.run(
                    ['git', 'clone', source_url, str(repo_dir)],
                    check=True
                )
                if 'tag' in self.release_config:
                    subprocess.run(
                        ['git', 'checkout', self.release_config['tag']],
                        cwd=str(repo_dir),
                        check=True
                    )
        else:
            raise ValueError(f"Unknown source type: {source_type}")

    def _build_plugin(self) -> None:
        """Build the plugin."""
        build_config = BuildConfigResolver.get_build_config(
            self.release_config['build'],
            self.platform
        )

        if not build_config:
            raise ValueError(f"No build configuration for platform {self.platform}")

        # Execute build commands
        dep_builder = DependencyBuilder(str(self.workdir), self.prefixdir, self.platform, self.nproc)
        dep_builder.env = self.env  # Use same environment
        dep_builder._execute_build(build_config)

    def _collect_artifacts(self) -> List[str]:
        """
        Collect build artifacts.

        Returns:
            List of artifact paths
        """
        artifacts_config = self.release_config.get('artifacts', {})
        if not artifacts_config:
            print("Warning: No artifacts defined")
            return []

        artifact_patterns = BuildConfigResolver.get_artifacts(artifacts_config, self.platform)

        artifacts = []
        for pattern in artifact_patterns:
            # Substitute variables in pattern
            artifact_path = EnvironmentManager.substitute_vars(pattern, self.env)

            if not Path(artifact_path).exists():
                raise FileNotFoundError(f"Artifact not found: {artifact_path}")

            artifacts.append(artifact_path)

        return artifacts


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Build VapourSynth plugin')
    parser.add_argument('--plugin', required=True, help='Plugin name')
    parser.add_argument('--version', required=True, help='Plugin version')
    parser.add_argument('--platform', required=True, help='Target platform')
    parser.add_argument('--workdir', required=True, help='Working directory')
    parser.add_argument('--prefixdir', help='Installation prefix directory')
    parser.add_argument('--plugins-dir', default='plugins', help='Plugins directory')
    parser.add_argument('--nproc', type=int, help='Number of parallel jobs (default: CPU count)')

    args = parser.parse_args()

    # Determine number of parallel jobs
    if args.nproc:
        nproc = args.nproc
    else:
        # Default to CPU count
        nproc = os.cpu_count() or 1

    try:
        builder = PluginBuilder(
            plugin_name=args.plugin,
            version=args.version,
            platform=args.platform,
            workdir=args.workdir,
            prefixdir=args.prefixdir,
            plugins_dir=args.plugins_dir,
            nproc=nproc
        )

        artifacts = builder.build()

        # Output artifacts (one per line for easy parsing)
        print("\nARTIFACTS:")
        for artifact in artifacts:
            print(artifact)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
