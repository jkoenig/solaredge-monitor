"""On-disk cache for battery presence (API-03).

Stores only {"version", "has_battery", "site_hash"}; no serial numbers and
no plain site id. To force a new detection, delete the cache file (a
sibling of the token file named ".battery.json").
"""

import contextlib
import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Union

FILE_VERSION = 1


def _site_hash(site_id: str) -> str:
    return hashlib.sha256(str(site_id).encode("utf-8")).hexdigest()[:16]


def load_battery_cache(path: Union[str, Path], site_id: str) -> Optional[bool]:
    """Return cached battery presence, or None if unknown (detect again)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    except FileNotFoundError:
        return None
    except OSError:
        logging.info("Battery cache missing or invalid, will detect")
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        data = None
    if (
        not isinstance(data, dict)
        or isinstance(data.get("version"), bool)
        or data.get("version") != FILE_VERSION
        or data.get("site_hash") != _site_hash(site_id)
        or not isinstance(data.get("has_battery"), bool)
    ):
        logging.info("Battery cache missing or invalid, will detect")
        return None
    return data["has_battery"]


def save_battery_cache(path: Union[str, Path], site_id: str, has_battery: bool) -> bool:
    """Atomically write the cache. Returns True if written, never raises on OSError."""
    target = Path(path)
    payload = json.dumps(
        {
            "version": FILE_VERSION,
            "has_battery": bool(has_battery),
            "site_hash": _site_hash(site_id),
        }
    ).encode("utf-8")
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(
            dir=target.parent, prefix=target.name + ".", suffix=".tmp"
        )
        try:
            os.fchmod(fd, 0o600)
            view = memoryview(payload)
            while view:
                written = os.write(fd, view)
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, target)
        return True
    except OSError:
        logging.warning("Could not write battery cache")
        if tmp is not None:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
        return False
    except BaseException:
        if tmp is not None:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
        raise
