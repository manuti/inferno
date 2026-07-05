"""Shared filesystem helpers for Inferno."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically write ``payload`` as JSON to ``path`` (best-effort).

    Writes to a temp file in the destination directory and ``os.replace``\\s it
    into place so readers never observe a partial file. Failures are logged and
    swallowed rather than raised, matching the persistence semantics the model
    registry and runtime settings rely on.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload))
        os.replace(tmp_name, path)
    except OSError:
        logger.warning("Could not persist JSON state to %s", path, exc_info=True)
