"""
CalDAV Automata — entry point.

Loads configuration from the file pointed at by the CONFIG_FILE environment
variable (default: /config/calendar.yaml) and starts the polling daemon.
"""

from __future__ import annotations

import logging
import os
import sys

from .config import load_config
from .daemon import Daemon

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    stream=sys.stdout,
)


def main() -> None:
    version = os.environ.get("APP_VERSION", "dev")
    logging.info("CalDAV Automata %s starting", version)

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
