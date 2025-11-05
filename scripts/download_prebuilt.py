#!/usr/bin/env python3
"""
Download pre-built toolchains and VapourSynth from GitHub releases.
Used in main build workflow to fetch pre-built dependencies.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path


def get_latest_release(repo: str, tag_prefix: str) -> dict:
    """
    Get the latest release matching a tag prefix.

    Args:
        repo: Repository in format 'owner/repo'
        tag_prefix: Tag prefix to filter (e.g., 'toolchains-', 'vapoursynth-')

    Returns:
        Release information dict
    """
    api_url = f"https://api.github.com/repos/{repo}/releases"

    print(f"Fetching releases from {repo}...", file=sys.stderr)

    try:
        with urllib.request.urlopen(api_url) as response:
            releases = json.loads(response.read())
    except Exception as e:
        print(f"Error fetching releases: {e}", file=sys.stderr)
        sys.exit(1)

    # Filter releases by tag prefix
    matching_releases = [r for r in releases if r['tag_name'].startswith(tag_prefix)]

    if not matching_releases:
        print(f"No releases found with tag prefix '{tag_prefix}'", file=sys.stderr)
        sys.exit(1)

    # Return the most recent one
    latest = matching_releases[0]
    print(f"Found latest release: {latest['tag_name']}", file=sys.stderr)

    return latest


def download_asset(asset_url: str, dest_path: str) -> None:
    """
    Download a release asset.

    Args:
        asset_url: URL to download from
        dest_path: Destination file path
    """
    print(f"Downloading {asset_url}...", file=sys.stderr)
    print(f"  -> {dest_path}", file=sys.stderr)

    dest_path_obj = Path(dest_path)
    dest_path_obj.parent.mkdir(parents=True, exist_ok=True)

    try:
        urllib.request.urlretrieve(asset_url, dest_path)
        print(f"Downloaded successfully", file=sys.stderr)
    except Exception as e:
        print(f"Error downloading: {e}", file=sys.stderr)
        sys.exit(1)


def extract_archive(archive_path: str, dest_dir: str) -> None:
    """
    Extract tar.gz or .7z archive.

    Args:
        archive_path: Path to archive file
        dest_dir: Destination directory
    """
    print(f"Extracting {archive_path}...", file=sys.stderr)

    dest_path = Path(dest_dir)
    dest_path.mkdir(parents=True, exist_ok=True)

    archive_path_obj = Path(archive_path)

    if archive_path_obj.suffix in ['.gz', '.tgz'] or archive_path.endswith('.tar.gz'):
        # Extract tar.gz
        subprocess.run(
            ['tar', 'xzf', str(archive_path), '-C', str(dest_dir)],
            check=True
        )
    elif archive_path_obj.suffix == '.7z':
        # Extract 7z
        subprocess.run(
            ['7z', 'x', str(archive_path), f'-o{dest_dir}'],
            check=True
        )
    else:
        print(f"Unsupported archive format: {archive_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Extracted to {dest_dir}", file=sys.stderr)


def download_toolchain(repo: str, toolchain_type: str, dest_dir: str) -> str:
    """
    Download and extract a toolchain.

    Args:
        repo: Repository in format 'owner/repo'
        toolchain_type: Type of toolchain ('musl' or 'glibc')
        dest_dir: Destination directory

    Returns:
        Path to extracted toolchain
    """
    release = get_latest_release(repo, 'toolchains-')

    # Find the appropriate asset
    asset_name_patterns = {
        'musl': 'x86_64-linux-musl-toolchain.tar.gz',
        'glibc': 'x86_64-linux-glibc217-toolchain.tar.gz'
    }

    if toolchain_type not in asset_name_patterns:
        print(f"Unknown toolchain type: {toolchain_type}", file=sys.stderr)
        sys.exit(1)

    pattern = asset_name_patterns[toolchain_type]

    # Find matching asset
    asset = None
    for a in release['assets']:
        if a['name'] == pattern:
            asset = a
            break

    if not asset:
        print(f"Asset not found: {pattern}", file=sys.stderr)
        sys.exit(1)

    # Download
    archive_path = Path(dest_dir) / asset['name']
    download_asset(asset['browser_download_url'], str(archive_path))

    # Extract
    extract_archive(str(archive_path), dest_dir)

    # Return toolchain path
    if toolchain_type == 'musl':
        return str(Path(dest_dir) / 'x86_64-unknown-linux-musl')
    else:
        return str(Path(dest_dir) / 'x86_64-unknown-linux-gnu')


def download_vapoursynth(repo: str, version: str, platform: str, dest_dir: str) -> str:
    """
    Download and extract VapourSynth.

    Args:
        repo: Repository in format 'owner/repo'
        version: VapourSynth version (e.g., 'R70')
        platform: Platform name (e.g., 'linux-musl', 'linux-glibc', 'macos')
        dest_dir: Destination directory

    Returns:
        Path to extracted VapourSynth
    """
    release = get_latest_release(repo, f'vapoursynth-{version}')

    # Find the appropriate asset
    asset_name_patterns = {
        'linux-musl': f'vapoursynth-{version}-linux-musl.tar.gz',
        'linux-glibc': f'vapoursynth-{version}-linux-glibc.tar.gz',
        'macos': f'vapoursynth-{version}-macos.tar.gz',
    }

    if platform not in asset_name_patterns:
        print(f"Unknown platform: {platform}", file=sys.stderr)
        sys.exit(1)

    pattern = asset_name_patterns[platform]

    # Find matching asset
    asset = None
    for a in release['assets']:
        if a['name'] == pattern:
            asset = a
            break

    if not asset:
        print(f"Asset not found: {pattern}", file=sys.stderr)
        sys.exit(1)

    # Download
    archive_path = Path(dest_dir) / asset['name']
    download_asset(asset['browser_download_url'], str(archive_path))

    # Extract
    extract_archive(str(archive_path), dest_dir)

    return str(Path(dest_dir))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Download pre-built toolchains and VapourSynth')
    parser.add_argument(
        '--type',
        choices=['toolchain', 'vapoursynth'],
        required=True,
        help='Type of package to download'
    )
    parser.add_argument(
        '--repo',
        default='OWNER/REPO',  # Replace with actual repo
        help='GitHub repository (owner/repo)'
    )
    parser.add_argument(
        '--toolchain-type',
        choices=['musl', 'glibc'],
        help='Toolchain type (for --type toolchain)'
    )
    parser.add_argument(
        '--version',
        help='VapourSynth version (for --type vapoursynth)'
    )
    parser.add_argument(
        '--platform',
        help='Platform (for --type vapoursynth)'
    )
    parser.add_argument(
        '--dest',
        required=True,
        help='Destination directory'
    )

    args = parser.parse_args()

    if args.type == 'toolchain':
        if not args.toolchain_type:
            print("Error: --toolchain-type is required for toolchain downloads", file=sys.stderr)
            sys.exit(1)

        toolchain_path = download_toolchain(args.repo, args.toolchain_type, args.dest)
        print(f"\nToolchain installed to: {toolchain_path}")
        print(f"\nTo use this toolchain, run:")
        print(f"  export PATH=\"{toolchain_path}/bin:$PATH\"")

        if args.toolchain_type == 'musl':
            print(f"  export CC=x86_64-unknown-linux-musl-gcc")
            print(f"  export CXX=x86_64-unknown-linux-musl-g++")
        else:
            print(f"  export CC=x86_64-unknown-linux-gnu-gcc")
            print(f"  export CXX=x86_64-unknown-linux-gnu-g++")

    elif args.type == 'vapoursynth':
        if not args.version or not args.platform:
            print("Error: --version and --platform are required for VapourSynth downloads", file=sys.stderr)
            sys.exit(1)

        vs_path = download_vapoursynth(args.repo, args.version, args.platform, args.dest)
        print(f"\nVapourSynth installed to: {vs_path}")


if __name__ == '__main__':
    main()
