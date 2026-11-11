"""Final fetch cadence for Phase 13 (QUOTA-01, D-02/D-05..D-09).

All cadence rules live here. FetchPlan never reads the clock; callers pass a
timezone-aware site-local `now`.

Day window 07:00-20:00 (poll every 30 min, 26 rounds):
- overview every poll, storage hourly, history once a day (= 2 calls),
  temperature twice a day (am/pm slot), devices only while unknown.
Night window 20:00-07:00: only STORAGE, one attempt per night slot at
23:00, 02:00 and 05:00 (a slot fires at the first poll at or after its hour
and before the next slot). No overview, history, temperature or devices.

Quota modes (passed to due()):
- "ok": full schedule above.
- "brake": overview at most hourly, no night slots (D-08).
- "stopped": due() returns an empty set (D-09).

Budget, all-success 24 h at 30-min polls: overview 26, storage 13 + 3 night,
history 1 (= 2 calls), temperature 2 -> 46 FetchPlan-level calls (about 58/day
with token refreshes counted as 1 credit). Brake: 30 FetchPlan-level calls.
Stopped: 0. After 3 consecutive failed overview rounds the plan is in backoff
(see in_backoff) and runs at most one round per hour until an overview
succeeds.

Slot state (history, temperature, night storage) persists via
to_dict()/load_dict() so a restart does not repeat a done slot (D-06).
Overview/storage timestamps are not persisted: the first round after a
restart fetches them again (accepted).
"""

import logging
import re
from datetime import date, datetime, timedelta
from typing import Dict, Optional, Set, Tuple

MODE_OK = "ok"
MODE_BRAKE = "brake"
MODE_STOPPED = "stopped"

OVERVIEW = "overview"
STORAGE = "storage"
HISTORY = "history"
TEMPERATURE = "temperature"
DEVICES = "devices"

_JOBS = (OVERVIEW, STORAGE, HISTORY, TEMPERATURE, DEVICES)


class FetchPlan:
    """Decides which fetch jobs are due and tracks their outcomes."""

    HISTORY_CALLS = 2  # production energy + consumption meters (D-10)

    def __init__(
        self,
        storage_interval: timedelta = timedelta(minutes=55),
        retry_after: timedelta = timedelta(minutes=60),
        max_attempts_per_slot: int = 3,
        devices_retry_after: timedelta = timedelta(hours=6),
        midday_hour: int = 12,
        overview_backoff_after: int = 3,
        overview_backoff_interval: timedelta = timedelta(minutes=60),
        night_start_hour: int = 20,
        night_end_hour: int = 7,
        night_storage_hours: tuple = (23, 2, 5),
        brake_overview_interval: timedelta = timedelta(minutes=55),
    ):
        self.storage_interval = storage_interval
        self.retry_after = retry_after
        self.max_attempts_per_slot = max_attempts_per_slot
        self.devices_retry_after = devices_retry_after
        self.midday_hour = midday_hour
        self.overview_backoff_after = overview_backoff_after
        self.overview_backoff_interval = overview_backoff_interval
        self.night_start_hour = night_start_hour
        self.night_end_hour = night_end_hour
        self.night_storage_hours = tuple(night_storage_hours)
        self.brake_overview_interval = brake_overview_interval

        self._overview_failures = 0
        self._last_overview_attempt: Optional[datetime] = None
        self._last_storage_attempt: Optional[datetime] = None
        self._last_devices_attempt: Optional[datetime] = None
        # slot key (job, date, slot-or-None) -> [attempts, succeeded, last_attempt]
        self._slots: Dict[Tuple, list] = {}

    @property
    def in_backoff(self) -> bool:
        return self._overview_failures >= self.overview_backoff_after

    def is_night(self, now: datetime) -> bool:
        start, end, hour = self.night_start_hour, self.night_end_hour, now.hour
        if start == end:
            return False
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end

    def _night_slot_hour(self, now: datetime) -> Optional[int]:
        """Hour of the current night storage slot, or None."""
        start = self.night_start_hour
        length = ((self.night_end_hour - start) % 24) * 60
        now_offset = ((now.hour - start) % 24) * 60 + now.minute
        best = None
        best_offset = -1
        for h in self.night_storage_hours:
            offset = ((h - start) % 24) * 60
            if offset < length and offset <= now_offset and offset > best_offset:
                best, best_offset = h, offset
        return best

    def _night_date(self, now: datetime) -> date:
        if now.hour >= self.night_start_hour:
            return now.date()
        return now.date() - timedelta(days=1)

    def _slot_key(self, job: str, now: datetime) -> Tuple:
        """Key shape (job, date, slot-or-None), shared with to_dict/load_dict."""
        if job == HISTORY:
            return (HISTORY, now.date(), None)
        if job == STORAGE:
            hour = self._night_slot_hour(now)
            return (STORAGE, self._night_date(now), f"n{hour:02d}")
        slot = "am" if now.hour < self.midday_hour else "pm"
        return (TEMPERATURE, now.date(), slot)

    def _slot_due(self, job: str, now: datetime) -> bool:
        state = self._slots.get(self._slot_key(job, now))
        if state is None:
            return True
        attempts, succeeded, last = state
        if succeeded or attempts >= self.max_attempts_per_slot:
            return False
        return now - last >= self.retry_after

    def due(
        self,
        now: datetime,
        has_battery: bool,
        battery_known: bool,
        mode: str = MODE_OK,
    ) -> Set[str]:
        if mode == MODE_STOPPED:
            return set()
        if self.is_night(now):
            if (
                mode == MODE_OK
                and has_battery
                and self._night_slot_hour(now) is not None
                and self._slot_key(STORAGE, now) not in self._slots
            ):
                return {STORAGE}
            return set()

        if (
            self.in_backoff
            and self._last_overview_attempt is not None
            and now - self._last_overview_attempt < self.overview_backoff_interval
        ):
            return set()

        jobs: Set[str] = set()
        last_ov = self._last_overview_attempt
        if (
            mode != MODE_BRAKE
            or last_ov is None
            or now - last_ov >= self.brake_overview_interval
        ):
            jobs.add(OVERVIEW)
        if has_battery:
            last = self._last_storage_attempt
            if last is None or now - last >= self.storage_interval:
                jobs.add(STORAGE)
            if self._slot_due(TEMPERATURE, now):
                jobs.add(TEMPERATURE)
        if self._slot_due(HISTORY, now):
            jobs.add(HISTORY)
        if not battery_known:
            last = self._last_devices_attempt
            if last is None or now - last >= self.devices_retry_after:
                jobs.add(DEVICES)
        return jobs

    def record(self, job: str, now: datetime, success: bool) -> None:
        if job not in _JOBS:
            raise ValueError(f"unknown job: {job}")
        if job == OVERVIEW:
            self._last_overview_attempt = now
            self._overview_failures = 0 if success else self._overview_failures + 1
        elif job == STORAGE:
            self._last_storage_attempt = now
            if self.is_night(now) and self._night_slot_hour(now) is not None:
                self._record_slot(job, now, success)
        elif job == DEVICES:
            self._last_devices_attempt = now
        else:
            self._record_slot(job, now, success)

    def _record_slot(self, job: str, now: datetime, success: bool) -> None:
        key = self._slot_key(job, now)
        state = self._slots.setdefault(key, [0, False, now])
        state[0] += 1
        state[1] = state[1] or success
        state[2] = now

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "slots": [
                {
                    "job": job,
                    "date": d.isoformat(),
                    "slot": slot,
                    "attempts": attempts,
                    "succeeded": succeeded,
                    "last": last.isoformat(),
                }
                for (job, d, slot), (attempts, succeeded, last) in self._slots.items()
            ],
        }

    def load_dict(self, data: dict, now: datetime) -> None:
        if not isinstance(data, dict) or data.get("version") != 1:
            return
        entries = data.get("slots")
        if not isinstance(entries, list):
            return
        cutoff = now.date() - timedelta(days=1)
        skipped = 0
        loaded: Dict[Tuple, list] = {}
        for e in entries:
            try:
                job, slot = e["job"], e["slot"]
                attempts, succeeded = e["attempts"], e["succeeded"]
                if job not in (HISTORY, TEMPERATURE, STORAGE):
                    raise ValueError("job")
                if (
                    isinstance(attempts, bool)
                    or not isinstance(attempts, int)
                    or attempts < 0
                    or not isinstance(succeeded, bool)
                ):
                    raise ValueError("fields")
                if job == HISTORY and slot is not None:
                    raise ValueError("slot")
                if job == TEMPERATURE and slot not in ("am", "pm"):
                    raise ValueError("slot")
                if job == STORAGE and not (
                    isinstance(slot, str) and re.fullmatch(r"n\d\d", slot)
                ):
                    raise ValueError("slot")
                d = date.fromisoformat(e["date"])
                last = datetime.fromisoformat(e["last"])
                if last.tzinfo is None:
                    raise ValueError("naive")
            except (KeyError, TypeError, ValueError):
                skipped += 1
                continue
            if d < cutoff:
                continue
            loaded[(job, d, slot)] = [attempts, succeeded, last]
        if skipped:
            logging.info("Ignored invalid fetch state entries")
        self._slots.update(loaded)
