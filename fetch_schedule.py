"""Interim fetch cadence for Phase 12 (D-07).

Phase 13 replaces this module with the final 07:00-20:00 schedule and the
persistent call counter; keep all cadence rules here.

Expected daily budget (poll every 30 min from 07:00 to 19:30, 26 rounds):
- All-success day: overview 26, storage 13, history 1 (= 2 calls, D-10),
  temperature 2 -> 43 FetchPlan-level calls (+ about 7 token refreshes,
  roughly 50/day).
- All-failure day: after 3 consecutive failed overview rounds the plan is
  in backoff (see in_backoff) and runs at most one round per hour until an
  overview succeeds. Overview 14, storage 13, history 3 attempts (= 6),
  temperature 6 -> 39 FetchPlan-level calls. Worst case at HTTP level is
  about 56: 39 + 3 overview retries outside backoff + at most 14 token
  refresh attempts (one per round). Both are within the ~60/day target.

State is in memory only: a service restart re-fetches history and the
current temperature slot (accepted for the interim). FetchPlan never reads
the clock; callers pass a timezone-aware site-local `now`.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Set, Tuple

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
    ):
        self.storage_interval = storage_interval
        self.retry_after = retry_after
        self.max_attempts_per_slot = max_attempts_per_slot
        self.devices_retry_after = devices_retry_after
        self.midday_hour = midday_hour
        self.overview_backoff_after = overview_backoff_after
        self.overview_backoff_interval = overview_backoff_interval

        self._overview_failures = 0
        self._last_overview_attempt: Optional[datetime] = None
        self._last_storage_attempt: Optional[datetime] = None
        self._last_devices_attempt: Optional[datetime] = None
        # slot key -> [attempts, succeeded, last_attempt]
        self._slots: Dict[Tuple, list] = {}

    @property
    def in_backoff(self) -> bool:
        return self._overview_failures >= self.overview_backoff_after

    def _slot_key(self, job: str, now: datetime) -> Tuple:
        if job == HISTORY:
            return (HISTORY, now.date())
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

    def due(self, now: datetime, has_battery: bool, battery_known: bool) -> Set[str]:
        if (
            self.in_backoff
            and self._last_overview_attempt is not None
            and now - self._last_overview_attempt < self.overview_backoff_interval
        ):
            return set()

        jobs = {OVERVIEW}
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
        elif job == DEVICES:
            self._last_devices_attempt = now
        else:
            key = self._slot_key(job, now)
            state = self._slots.setdefault(key, [0, False, now])
            state[0] += 1
            state[1] = state[1] or success
            state[2] = now
