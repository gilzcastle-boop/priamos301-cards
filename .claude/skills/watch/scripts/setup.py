#!/usr/bin/env python3
"""Dependency check for the watch skill.

Reports only. It installs nothing, downloads nothing and writes nothing; when a tool is
missing it prints the command a person can run themselves.
"""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys

from config import get_config
from runtime import configure_stdio, run_text

REQUIRED_BINARIES = ['ffmpeg', 'ffprobe']   # enough for local video files
URL_BINARY = 'yt-dlp'                       # only needed when the source is a URL


def _version(name: str, path: str) -> str | None:
    try:
        result = run_text([path, '--version' if name == URL_BINARY else '-version'], timeout=20)
    except SystemExit:
        return None
    output = result.stdout or result.stderr
    return output.splitlines()[0] if result.returncode == 0 and output else None


def install_hints(missing: list[str], system: str) -> list[str]:
    """Commands for a person to run. This script never runs them."""
    need_ffmpeg = any(name in missing for name in REQUIRED_BINARIES)
    need_ytdlp = URL_BINARY in missing
    hints = []
    if system == 'Darwin':
        if need_ffmpeg:
            hints.append('brew install ffmpeg')
        if need_ytdlp:
            hints.append('brew install yt-dlp   (only for URLs)')
    elif system == 'Windows':
        if need_ffmpeg:
            hints.append('winget install --id Gyan.FFmpeg --exact')
        if need_ytdlp:
            hints.append('winget install --id yt-dlp.yt-dlp --exact   (only for URLs)')
            hints.append('winget install --id DenoLand.Deno --exact   (only for YouTube URLs)')
    else:
        if need_ffmpeg:
            hints.append('sudo apt install ffmpeg   (or the equivalent package for your distribution)')
        if need_ytdlp:
            hints.append('pipx install "yt-dlp[default,curl-cffi]"   (only for URLs; YouTube also needs Deno)')
    return hints


def status() -> dict:
    system = platform.system()
    tools = {}
    for name in (*REQUIRED_BINARIES, URL_BINARY):
        path = shutil.which(name)
        tools[name] = {'path': path, 'version': _version(name, path) if path else None}
    missing = [name for name in REQUIRED_BINARIES if not tools[name]['path']]
    url_ready = bool(tools[URL_BINARY]['path'])
    return {
        'can_proceed': not missing,
        'missing_binaries': missing,
        'local_files': not missing,
        'url_sources': url_ready and not missing,
        'tools': tools,
        'deno': shutil.which('deno'),
        'watch_detail': get_config()['detail'],
        'platform': system,
        'install_hints': install_hints(missing + ([] if url_ready else [URL_BINARY]), system),
        'network_use': 'none for local files; yt-dlp contacts the video site only when the source is a URL',
        'keys_needed': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='Silent preflight: exit 0 when local files can be watched')
    mode.add_argument('--json', action='store_true', help='Print the full status as JSON')
    args = parser.parse_args()
    report = status()
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    if args.check:
        if report['can_proceed']:
            return 0
        print(f"[watch] Missing {', '.join(report['missing_binaries'])}.", file=sys.stderr)
        return 2
    print('[watch] local video files: ' + ('ready' if report['local_files'] else
                                           f"missing {', '.join(report['missing_binaries'])}"))
    print('[watch] URLs: ' + ('ready (yt-dlp found)' if report['url_sources'] else 'not available (yt-dlp is not installed)'))
    for hint in report['install_hints']:
        print(f'[watch] to install yourself: {hint}')
    return 0 if report['can_proceed'] else 2


if __name__ == '__main__':
    configure_stdio()
    raise SystemExit(main())
