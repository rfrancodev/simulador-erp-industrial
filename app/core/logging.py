"""Logging setup for the application.

Call :func:`setup_logging` once at application startup. Loggers should be
obtained via ``logging.getLogger(__name__)`` throughout the codebase and must
never emit sensitive data.

Logging policy:
    - NEVER log passwords, tokens, JWT payloads, or the ``Authorization`` header.
    - NEVER log request/response bodies that may contain credentials.
    - Logging business identifiers (entity codes, order numbers, usernames) is
      acceptable; these are not secrets.
    - The database URL is logged with the credentials stripped
      (see ``app/database/connection.py``).
"""

from __future__ import annotations

import logging
import sys

_LOGGING_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root logger idempotently with a stdout handler."""
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOGGING_FORMAT))
    root.addHandler(handler)
    root.setLevel(level)