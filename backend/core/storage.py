"""
Persistence self-check for the data directory.

Whether backend/data survives a deploy depends on the host: on Render it needs a
disk mounted at that path, and a service created outside the blueprint may have
none. That cannot be determined from inside the code, but it can be measured —
this writes a marker on first boot and counts every boot after it.

If first_seen keeps its value across a redeploy while boots increases, the
directory is persistent. If first_seen resets to the current time, it is not,
and everything written there is being discarded on each deploy.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from core.config import DATA_DIR

logger = logging.getLogger(__name__)

MARKER_PATH = DATA_DIR / "storage_marker.json"

_state: dict[str, Any] = {}


def record_boot() -> dict[str, Any]:
    """Stamp this boot into the marker file and return the resulting state."""
    global _state
    now = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")

    previous: dict[str, Any] = {}
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if MARKER_PATH.is_file():
            previous = json.loads(MARKER_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Could not read storage marker: {e}")

    first_seen = previous.get("first_seen") or now
    boots = int(previous.get("boots", 0)) + 1

    _state = {
        "first_seen": first_seen,
        "last_boot": now,
        "boots": boots,
        # A marker that was already on disk is itself the proof: it outlived the
        # boot that wrote it. Comparing timestamps instead would misreport two
        # starts landing in the same second.
        "persisted": bool(previous),
    }

    try:
        MARKER_PATH.write_text(json.dumps(_state), encoding="utf-8")
    except Exception as e:
        logger.error(f"Could not write storage marker to {MARKER_PATH}: {e}")
        _state["writable"] = False
        return _state

    _state["writable"] = True

    if _state["persisted"]:
        logger.info(
            f"Data directory is persistent (first seen {first_seen}, boot #{boots})"
        )
    else:
        logger.warning(
            "Data directory shows no history yet. If this message appears on "
            "every deploy, backend/data is NOT on a persistent volume and "
            "analytics, feedback and community art are being lost each time."
        )
    return _state


def storage_state() -> Optional[dict[str, Any]]:
    """Return the state recorded at boot, or None if it never ran."""
    return _state or None
