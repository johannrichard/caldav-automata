"""
Configuration loader for CalDAV Automata.

Reads a YAML file and expands ``${ENV_VAR}`` references in string values so
that secrets can be kept out of the config file and supplied via environment
variables or file-backed secret mounts such as Docker secrets.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

_ENV_RE = re.compile(r"\$\{([^}]+)\}")


def _expand(value: object) -> object:
    """Recursively expand ``${VAR}`` placeholders in strings."""
    if isinstance(value, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), m.group(0)), value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


def _load_secret(path: str) -> str:
    """Load a secret from *path*, trimming only trailing newlines."""
    try:
        return Path(path).read_text(encoding="utf-8").rstrip("\r\n")
    except OSError as exc:
        raise OSError(f"Could not read password_file {path!r}: {exc}") from exc


def _resolve_account_secrets(config: dict) -> dict:
    """Resolve file-backed account secrets into plain ``password`` values."""
    accounts = config.get("accounts")
    if not isinstance(accounts, list):
        return config

    resolved_accounts: list[dict] = []
    for account in accounts:
        if not isinstance(account, dict):
            resolved_accounts.append(account)
            continue

        resolved = dict(account)
        password = resolved.get("password")
        password_file = resolved.get("password_file")
        if not password and password_file:
            resolved["password"] = _load_secret(str(password_file))
        resolved_accounts.append(resolved)

    return {**config, "accounts": resolved_accounts}


def load_config(path: str) -> dict:
    """
    Load and return the daemon configuration from *path*.

    Environment variables referenced as ``${VAR}`` are substituted in place.
    Account entries may also specify ``password_file`` to load a password
    from a mounted secret file.
    """
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return _resolve_account_secrets(_expand(raw or {}))
