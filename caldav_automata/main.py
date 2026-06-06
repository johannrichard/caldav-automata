"""
CalDAV Automata — entry point.

Loads configuration from the file pointed at by the CONFIG_FILE environment
variable (default: /config/calendar.yaml) and starts the polling daemon.
"""

from __future__ import annotations

import logging
import os
import sys
from importlib.metadata import PackageNotFoundError, version

from .config import load_config
from .daemon import Daemon


class _AnsiColorFormatter(logging.Formatter):
    _RESET = "\033[0m"
    _LEVEL_COLORS = {
        logging.DEBUG: "\033[36m",  # cyan
        logging.INFO: "\033[32m",  # green
        logging.WARNING: "\033[33m",  # yellow
        logging.ERROR: "\033[31m",  # red
        logging.CRITICAL: "\033[1;31m",  # bold red
    }

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        color = self._LEVEL_COLORS.get(record.levelno, "")
        if not color:
            return base
        return f"{color}{base}{self._RESET}"


def _want_color_logs() -> bool:
    mode = os.environ.get("LOG_COLOR", "auto").strip().lower()
    if mode in {"0", "false", "off", "never"}:
        return False
    if mode in {"1", "true", "on", "always"}:
        return True

    # auto mode: honor NO_COLOR and only colorize on a real TTY.
    if os.environ.get("NO_COLOR") is not None:
        return False
    return sys.stdout.isatty() and os.environ.get("TERM", "") != "dumb"


def _configure_logging() -> None:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    fmt = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"

    handler = logging.StreamHandler(sys.stdout)
    if _want_color_logs():
        handler.setFormatter(_AnsiColorFormatter(fmt))
    else:
        handler.setFormatter(logging.Formatter(fmt))

    logging.basicConfig(level=level, handlers=[handler])


_configure_logging()


def _resolve_app_version() -> str:
    """Return installed package version, then APP_VERSION, then 'dev'."""
    try:
        return version("caldav-automata")
    except PackageNotFoundError:
        return os.environ.get("APP_VERSION", "dev")


def main() -> None:
    app_version = _resolve_app_version()
    logging.info("CalDAV Automata %s starting", app_version)

    config_file = os.environ.get("CONFIG_FILE", "/config/calendar.yaml")
    try:
        config = load_config(config_file)
    except FileNotFoundError:
        logging.critical("Config file not found: %s", config_file)
        sys.exit(1)
    except Exception as exc:
        logging.critical("Failed to load config: %s", exc)
        sys.exit(1)

    Daemon(config).run()


if __name__ == "__main__":
    main()
