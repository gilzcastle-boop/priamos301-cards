#!/usr/bin/env python3
"""Watch settings: command line first, then two environment variables, then defaults.

This build keeps no configuration file and no keys: nothing is read from or written to the
home directory or to a project .env.
"""
from __future__ import annotations

import os

DEFAULT_DETAIL = 'balanced'
DETAILS = {'transcript', 'efficient', 'balanced', 'token-burner'}


def get_config() -> dict:
    detail = os.environ.get('WATCH_DETAIL', DEFAULT_DETAIL).strip()
    return {
        'detail': detail if detail in DETAILS else DEFAULT_DETAIL,
        'sub_lang': os.environ.get('WATCH_SUB_LANG', '').strip() or 'auto',
    }


def frame_cap(detail: str) -> int | None:
    return {'efficient': 50, 'balanced': 100, 'token-burner': None, 'transcript': None}.get(detail, 100)
