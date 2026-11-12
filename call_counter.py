"""
Persistent SolarEdge call counter (single source of truth for the credit budget).

Stored in the counter file (JSON, mode 600, written atomically):
    - cycle start date, cycle total and the "stopped" flag
    - per-day totals with per-endpoint counts (current and previous billing
      cycle only)
    - one-shot log flags (soft brake / hard stop / last day summary)
    - the fetch state blob of the FetchPlan (so it survives restarts)

NOT stored: site id, tokens, serials, URLs. Only endpoint names, dates and
counts.

Counting rule: every SolarEdge HTTP attempt counts, including retries,
failures and token refresh POSTs. Forecast.Solar calls are not counted.
The count is persisted BEFORE the call is sent, so a crash can only
over-count, never under-count. If the counter cannot be persisted, the call
is refused (fail closed).

The billing cycle resets at 00:00 Europe/Zurich on the configured billing day
(a billing day that does not exist in a month falls back to the last day of
that month). The limits are constants, not configuration, so a typo in .env
can never raise the stop above the real credit pool.

This module imports no other project module (avoids import cycles).
"""

import calendar
import contextlib
import fcntl
import json
import logging
import os
import tempfile
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, List, Optional, Union
from zoneinfo import ZoneInfo

SITE_TZ = ZoneInfo("Europe/Zurich")
FILE_VERSION = 1
DEFAULT_BILLING_DAY = 5
SOFT_LIMIT = 1500
HARD_LIMIT = 1800

OK = "ok"
BRAKE = "brake"
STOPPED = "stopped"

ENDPOINT_ORDER = ("overview", "storage", "history", "temperature", "devices", "token", "other")


class QuotaBlocked(Exception):
    """Raised by CallCounter.acquire when no call may be sent."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def endpoint_for_url(url: str) -> str:
    """Map a SolarEdge URL to a counter endpoint name (query string ignored)."""
    path = urllib.parse.urlsplit(url).path.rstrip("/")
    if path.endswith("/oauth2/token"):
        return "token"
    if path.endswith("/storage/telemetry"):
        return "storage"
    if path.endswith("/storage/status"):
        return "temperature"
    if path.endswith("/meters/telemetry"):
        return "history"
    if path.endswith("/energy"):
        return "history"
    if path.endswith("/overview"):
        return "overview"
    if path.endswith("/devices"):
        return "devices"
    return "other"


def reset_date(year: int, month: int, billing_day: int) -> date:
    """Reset date of a month; billing day is clamped to the month length."""
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(billing_day, last))


def _prev_month(year: int, month: int):
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _next_month(year: int, month: int):
    return (year + 1, 1) if month == 12 else (year, month + 1)


def cycle_start_for(day: date, billing_day: int) -> date:
    """Start date of the billing cycle containing `day`."""
    this_reset = reset_date(day.year, day.month, billing_day)
    if day >= this_reset:
        return this_reset
    y, m = _prev_month(day.year, day.month)
    return reset_date(y, m, billing_day)


def next_reset_for(day: date, billing_day: int) -> date:
    """First day of the billing cycle after the one containing `day`."""
    start = cycle_start_for(day, billing_day)
    y, m = _next_month(start.year, start.month)
    return reset_date(y, m, billing_day)


_HELD_LOCKS: dict = {}


def lock_path_for(counter_path: Union[str, Path]) -> Path:
    path = Path(counter_path)
    return path.with_name(path.name + ".lock")


def try_lock_counter(counter_path: Union[str, Path], hold: bool = False) -> bool:
    """Take a non-blocking exclusive flock on the counter's lock file.

    The service holds it for its whole lifetime (hold=True) so that no second
    writer (seed script, second instance) can clobber the in-memory count.
    Returns False only if another process holds it. If the lock file cannot be
    opened/created or flock fails for another reason (EACCES, missing directory,
    read-only FS ...), the OSError is raised so callers can tell "held" from
    "cannot lock". With hold=True the lock is kept (idempotent per path within
    a process); otherwise it is released at once (a pure "is anyone running"
    probe).
    """
    key = str(lock_path_for(counter_path))
    if key in _HELD_LOCKS:
        return True
    fd = os.open(key, os.O_RDWR | os.O_CREAT, 0o600)  # OSError propagates
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return False
    except OSError:
        os.close(fd)
        raise
    if hold:
        _HELD_LOCKS[key] = fd
    else:
        os.close(fd)  # closing releases the flock
    return True


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


class CallCounter:
    """Persistent call counter with billing-cycle reset, brake and hard stop."""

    def __init__(
        self,
        path: Union[str, Path],
        billing_day: int = DEFAULT_BILLING_DAY,
        soft_limit: int = SOFT_LIMIT,
        hard_limit: int = HARD_LIMIT,
        now_fn: Optional[Callable[[], datetime]] = None,
    ):
        self.path = Path(path)
        self.billing_day = billing_day
        self.soft_limit = soft_limit
        self.hard_limit = hard_limit
        self._now_fn = now_fn or (lambda: datetime.now(SITE_TZ))
        self._reset_state()
        self._load()

    # -- state helpers -----------------------------------------------------

    def _reset_state(self) -> None:
        self._cycle_start: Optional[date] = None
        self._cycle_total = 0
        self._stopped = False
        self._brake_logged = False
        self._stop_logged = False
        self._last_summary_day: Optional[date] = None
        self._days: dict = {}
        self._fetch_state: dict = {}

    def _load(self) -> None:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            corrupt = self.path.with_name(self.path.name + ".corrupt")
            if corrupt.exists():
                # An earlier fail-safe moved the bad file aside but its state
                # was never persisted: a missing file is NOT a clean start.
                self._fail_safe("missing while a .corrupt copy exists", move=False)
            return  # otherwise first start: nothing used yet
        except (OSError, UnicodeDecodeError) as exc:
            self._fail_safe(f"unreadable ({exc.__class__.__name__})")
            return
        try:
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get("version") != FILE_VERSION:
                raise ValueError("version")
            cycle_start = date.fromisoformat(data["cycle_start"])
            cycle_total = data["cycle_total"]
            stopped = data["stopped"]
            brake_logged = data["brake_logged"]
            stop_logged = data["stop_logged"]
            lsd = data.get("last_summary_day")
            last_summary = date.fromisoformat(lsd) if lsd is not None else None
            if not _is_int(cycle_total) or cycle_total < 0:
                raise ValueError("cycle_total")
            if not all(isinstance(v, bool) for v in (stopped, brake_logged, stop_logged)):
                raise ValueError("flags")
        except (ValueError, KeyError, TypeError, RecursionError):
            self._fail_safe("invalid content")
            return
        # History and fetch state are not authoritative: drop only bad parts,
        # never the totals above.
        days = {}
        days_raw = data.get("days", {})
        if not isinstance(days_raw, dict):
            logging.warning("Call counter: ignoring invalid days history")
            days_raw = {}
        for key, entry in days_raw.items():
            try:
                d = date.fromisoformat(key)
                total = entry["total"]
                after = entry["cycle_after"]
                eps = entry["endpoints"]
                if not (_is_int(total) and _is_int(after) and isinstance(eps, dict)):
                    raise ValueError("day")
                if not all(isinstance(k, str) and _is_int(v) for k, v in eps.items()):
                    raise ValueError("endpoints")
            except (ValueError, KeyError, TypeError):
                logging.warning("Call counter: dropping invalid day entry")
                continue
            days[d.isoformat()] = {
                "total": total,
                "cycle_after": after,
                "endpoints": dict(eps),
            }
        fetch_state = data.get("fetch_state", {})
        if not isinstance(fetch_state, dict):
            logging.warning("Call counter: ignoring invalid fetch state")
            fetch_state = {}
        self._cycle_start = cycle_start
        self._cycle_total = cycle_total
        self._stopped = stopped
        self._brake_logged = brake_logged
        self._stop_logged = stop_logged
        self._last_summary_day = last_summary
        self._days = days
        self._fetch_state = fetch_state

    def _fail_safe(self, why: str, move: bool = True) -> None:
        """Unusable counter file: keep it aside and start conservatively.

        Never start from 0 (that would grant a fresh budget). The true count
        is unknown, so start at the hard limit: no call is sent until the
        owner re-seeds the counter or the cycle resets.
        The fail-safe state is persisted at once so a restart before the first
        regular write cannot see "no file" and start at 0. If that write fails,
        the memory state stays at the hard limit, and the surviving `.corrupt`
        sibling makes the next start fail safe again (see `_load`).
        """
        self._reset_state()
        corrupt = self.path.with_name(self.path.name + ".corrupt")
        moved = True
        kept = f"kept as {corrupt.name}"
        if move:
            try:
                os.replace(self.path, corrupt)
            except OSError:
                moved = False
                kept = "could not be moved aside"
        self._cycle_start = cycle_start_for(self._today(None), self.billing_day)
        self._cycle_total = self.hard_limit
        if moved:
            # Do not overwrite a bad file that could not be moved aside: it
            # keeps triggering the fail-safe on the next start anyway.
            self._persist()
        logging.error(
            f"Call counter file {why} ({kept}); starting at the hard limit "
            f"{self.hard_limit}/{self.hard_limit} (stopped). Re-seed with "
            "scripts/seed_call_counter.py"
        )

    def _now(self, now: Optional[datetime]) -> datetime:
        return now if now is not None else self._now_fn()

    def _today(self, now: Optional[datetime]) -> date:
        return self._now(now).astimezone(SITE_TZ).date()

    def _roll(self, now: Optional[datetime]) -> date:
        today = self._today(now)
        cs = cycle_start_for(today, self.billing_day)
        # Only move forward so a changed billing day cannot lose counts
        if self._cycle_start is None or cs > self._cycle_start:
            self._cycle_start = cs
            self._cycle_total = 0
            self._stopped = False
            self._brake_logged = False
            self._stop_logged = False
            logging.info(f"Billing cycle reset: new cycle from {cs}, limit {self.hard_limit}")
        key = today.isoformat()
        if key not in self._days:
            self._days[key] = {
                "total": 0,
                "cycle_after": self._cycle_total,
                "endpoints": {},
            }
        return today

    def _next_reset(self, today: date) -> date:
        return next_reset_for(today, self.billing_day)

    def _is_stopped(self) -> bool:
        return self._stopped or self._cycle_total >= self.hard_limit

    def _log_hard_stop_once(self, today: date) -> None:
        if not self._stop_logged:
            self._stop_logged = True
            logging.warning(
                f"Call budget hard stop: {self._cycle_total}/{self.hard_limit} calls; "
                f"no API calls until {self._next_reset(today)}"
            )

    # -- persistence -------------------------------------------------------

    def _prune(self) -> None:
        if self._cycle_start is None:
            return
        keep_from = cycle_start_for(self._cycle_start - timedelta(days=1), self.billing_day)
        for key in list(self._days):
            if date.fromisoformat(key) < keep_from:
                del self._days[key]

    def _persist(self) -> bool:
        """Atomically write the counter file. Never raises OSError."""
        if self._cycle_start is None:
            self._roll(None)  # never persist a null cycle_start
        self._prune()
        payload = json.dumps(
            {
                "version": FILE_VERSION,
                "cycle_start": self._cycle_start.isoformat() if self._cycle_start else None,
                "cycle_total": self._cycle_total,
                "stopped": self._stopped,
                "brake_logged": self._brake_logged,
                "stop_logged": self._stop_logged,
                "last_summary_day": (
                    self._last_summary_day.isoformat() if self._last_summary_day else None
                ),
                "days": self._days,
                "fetch_state": self._fetch_state,
            },
            indent=1,
            sort_keys=True,
        ).encode("utf-8")
        target = self.path
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
            tmp = None
            self._fsync_dir(target.parent)
            return True
        except OSError:
            logging.warning("Could not write call counter file")
            if tmp is not None:
                with contextlib.suppress(OSError):
                    os.unlink(tmp)
            return False
        except BaseException:
            if tmp is not None:
                with contextlib.suppress(OSError):
                    os.unlink(tmp)
            raise

    @staticmethod
    def _fsync_dir(directory: Path) -> None:
        with contextlib.suppress(OSError):
            dfd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)

    # -- public API --------------------------------------------------------

    def state(self, now: Optional[datetime] = None) -> str:
        self._roll(now)
        if self._is_stopped():
            return STOPPED
        if self._cycle_total >= self.soft_limit:
            return BRAKE
        return OK

    def cycle_total(self, now: Optional[datetime] = None) -> int:
        self._roll(now)
        return self._cycle_total

    def next_reset(self, now: Optional[datetime] = None) -> date:
        return self._next_reset(self._roll(now))

    def acquire(self, endpoint: str, now: Optional[datetime] = None) -> None:
        """Count one call and persist before returning; raise QuotaBlocked if not allowed."""
        today = self._roll(now)
        if self._is_stopped():
            self._log_hard_stop_once(today)
            raise QuotaBlocked("stopped")
        self._cycle_total += 1
        day = self._days[today.isoformat()]
        day["total"] += 1
        day["endpoints"][endpoint] = day["endpoints"].get(endpoint, 0) + 1
        day["cycle_after"] = self._cycle_total
        if self._cycle_total == self.soft_limit and not self._brake_logged:
            self._brake_logged = True
            logging.warning(
                f"Call budget soft brake: {self._cycle_total}/{self.hard_limit} calls; "
                "reducing fetch frequency"
            )
        if self._cycle_total >= self.hard_limit:
            self._log_hard_stop_once(today)
        if not self._persist():
            logging.error("Could not persist call counter; call not sent")
            raise QuotaBlocked("counter not persisted")
        logging.debug(f"Counted call: {endpoint} (cycle {self._cycle_total}/{self.hard_limit})")

    def mark_exhausted(self, now: Optional[datetime] = None) -> None:
        """Stop until the next reset (SolarEdge reported the credit limit as
        reached, or kept answering 429; the caller logs which)."""
        today = self._roll(now)
        self._stopped = True
        if not self._stop_logged:
            self._stop_logged = True
            logging.error(
                "SolarEdge rejects calls (credit limit); "
                f"stopping API calls until {self._next_reset(today)}"
            )
        if not self._persist():
            logging.error(
                "Could not persist the stopped flag; the next start may send one more call"
            )

    def pop_day_summaries(self, now: Optional[datetime] = None) -> List[str]:
        """Return the one-line summary of yesterday, once."""
        today = self._roll(now)
        yesterday = today - timedelta(days=1)
        entry = self._days.get(yesterday.isoformat())
        if entry is None:
            return []
        if self._last_summary_day is not None and self._last_summary_day >= yesterday:
            return []
        parts = ", ".join(
            f"{name} {entry['endpoints'][name]}"
            for name in ENDPOINT_ORDER
            if entry["endpoints"].get(name, 0) > 0
        )
        group = f" ({parts})" if entry["total"] > 0 and parts else ""
        line = (
            f"Calls {yesterday}: {entry['total']}{group}; "
            f"cycle {entry['cycle_after']}/{self.hard_limit}"
        )
        self._last_summary_day = yesterday
        self._persist()
        return [line]

    def fetch_state(self) -> dict:
        return dict(self._fetch_state)

    def save_fetch_state(self, data: dict) -> bool:
        self._fetch_state = dict(data)
        return self._persist()

    def seed(self, total: int, now: Optional[datetime] = None, force: bool = False) -> int:
        """Set the cycle total (raise only unless force). Used by the seed script.

        Raises OSError if the counter file could not be written.
        """
        today = self._roll(now)
        self._cycle_total = total if force else max(self._cycle_total, total)
        if force:
            self._stopped = self._cycle_total >= self.hard_limit
            self._stop_logged = self._stopped
            self._brake_logged = self._cycle_total >= self.soft_limit
        self._days[today.isoformat()]["cycle_after"] = self._cycle_total
        if not self._persist():
            raise OSError("call counter file could not be written")
        return self._cycle_total
