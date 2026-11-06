"""On-disk cache for battery presence (API-03).

Stores only {"version", "has_battery", "site_hash", "checked_at"}; no serial
numbers and no plain site id. A True result is kept; a False result expires
after FALSE_TTL_SECONDS (7 days) so a temporarily inactive battery is
re-detected. A missing "checked_at" (older files) counts as expired for False.
To force a new detection, delete the cache file (a sibling of the token file
named ".battery.json").
"""

import contextlib
import hashlib
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple, Union

FILE_VERSION = 1
FALSE_TTL_SECONDS = 7 * 24 * 3600


def _site_hash(site_id: str) -> str:
    return hashlib.sha256(str(site_id).encode("utf-8")).hexdigest()[:16]


def is_false_expired(checked_at: Optional[float], now: Optional[float] = None) -> bool:
    """True if a cached has_battery=False entry is too old (or has no timestamp)."""
    if checked_at is None:
        return True
    now = time.time() if now is None else now
    return now - checked_at >= FALSE_TTL_SECONDS


def load_battery_cache(
    path: Union[str, Path], site_id: str, now: Optional[float] = None
) -> Optional[bool]:
    """Return cached battery presence, or None if unknown or expired (detect again)."""
    entry = load_battery_cache_entry(path, site_id)
    if entry is None:
        return None
    has_battery, checked_at = entry
    if not has_battery and is_false_expired(checked_at, now):
        logging.info("Cached 'no battery' expired, will detect")
        return None
    return has_battery


def load_battery_cache_entry(
    path: Union[str, Path], site_id: str
) -> Optional[Tuple[bool, Optional[float]]]:
    """Return (has_battery, checked_at) without applying expiry, or None if invalid."""
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
    checked_at = data.get("checked_at")
    if isinstance(checked_at, bool) or not isinstance(checked_at, (int, float)):
        checked_at = None
    return data["has_battery"], checked_at


def save_battery_cache(path: Union[str, Path], site_id: str, has_battery: bool) -> bool:
    """Atomically write the cache. Returns True if written, never raises on OSError."""
    target = Path(path)
    payload = json.dumps(
        {
            "version": FILE_VERSION,
            "has_battery": bool(has_battery),
            "site_hash": _site_hash(site_id),
            "checked_at": int(time.time()),
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
