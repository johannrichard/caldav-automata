"""
Configuration loader for CalDAV Automata.

Reads a YAML file and expands ``${ENV_VAR}`` references in string values so
that secrets can be kept out of the config file and supplied via environment
variables or Docker secrets.
"""

from __future__ import annotations

import os
import re

import yaml

_ENV_RE = re.compile(r'\$\{([^}]+)\}')


def _expand(value: object) -> object:
    """Recursively expand ``${VAR}`` placeholders in strings."""
    if isinstance(value, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), m.group(0)), value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


def load_config(path: str) -> dict:
    """
    Load and return the daemon configuration from *path*.

    Environment variables referenced as ``${VAR}`` are substituted in place.
    """
    with open(path, encoding='utf-8') as fh:
        raw = yaml.safe_load(fh)
    return _expand(raw or {})
