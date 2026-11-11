#!/usr/bin/env python3
"""One-off seed of the SolarEdge call counter (D-15).

Sets the current billing cycle's counter to the real usage so far, either from
an explicit count or by counting call lines in the service journal. Only a
count is written, never ids. An existing higher count is never lowered unless
--force is given.

Deploy procedure (executed in Phase 14, on raspberrypi.local, as user pi):
  1. Stop the service first. The running service keeps the counter in memory
     and would overwrite the file:
       sudo systemctl stop solaredge-monitor
  2. Seed from the journal since the cycle start, plus a margin for the manual
     probe and preview calls made outside the service:
       journalctl -u solaredge-monitor --since "YYYY-MM-DD 00:00" -o cat | venv/bin/python3 scripts/seed_call_counter.py --from-journal --margin 20
  3. Start the service again:
       sudo systemctl start solaredge-monitor

Or with a known number: scripts/seed_call_counter.py --count 300 --margin 20

Counting failed and timed-out attempts is deliberately conservative (D-13:
count wherever the request may have been sent).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from call_counter import (  # noqa: E402
    DEFAULT_BILLING_DAY,
    HARD_LIMIT,
    CallCounter,
    lock_path_for,
    try_lock_counter,
)

JOURNAL_MARKERS = (
    "API /sites/",
    "API timeout: /sites/",
    "API request failed: /sites/",
    "Access token refreshed",
    "Token refresh failed temporarily",
    "Token refresh rejected",
)


def count_journal_calls(lines: Iterable[str]) -> int:
    """Count journal lines that correspond to a SolarEdge request attempt."""
    return sum(1 for line in lines if any(m in line for m in JOURNAL_MARKERS))


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the SolarEdge call counter (one-off).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--count", type=int, help="explicit number of calls used this cycle")
    group.add_argument(
        "--from-journal", action="store_true", help="count call lines from journal text on stdin"
    )
    parser.add_argument(
        "--margin", type=int, default=20,
        help="extra calls for manual probe/preview calls outside the service (default 20)",
    )
    parser.add_argument("--file", help="counter file (default: SOLAREDGE_CALL_COUNTER_FILE or <repo>/.calls.json)")
    parser.add_argument("--billing-day", type=int, help="billing day (default: SOLAREDGE_BILLING_DAY or 5)")
    parser.add_argument("--force", action="store_true", help="allow lowering an existing higher count")
    args = parser.parse_args(argv)

    if args.from_journal:
        base = count_journal_calls(sys.stdin)
    else:
        base = args.count
    if base < 0 or args.margin < 0:
        print("Error: count and margin must be >= 0", file=sys.stderr)
        return 2

    path = args.file or os.environ.get("SOLAREDGE_CALL_COUNTER_FILE") or str(REPO_ROOT / ".calls.json")
    billing_day = args.billing_day
    if billing_day is None:
        try:
            billing_day = int(os.environ.get("SOLAREDGE_BILLING_DAY", DEFAULT_BILLING_DAY))
        except ValueError:
            print("Error: SOLAREDGE_BILLING_DAY must be an integer", file=sys.stderr)
            return 2

    if not 1 <= billing_day <= 31:
        print("Error: billing day must be between 1 and 31", file=sys.stderr)
        return 2

    # The service holds an flock on <file>.lock while running: refuse to seed
    # then, its in-memory count would overwrite the seeded value.
    try:
        locked = try_lock_counter(path)
    except OSError as exc:
        print(
            f"Error: cannot open or lock the counter lock file "
            f"{lock_path_for(path)} ({exc}); this is a permission or filesystem "
            "problem, not a running service. Fix ownership of the file or "
            "re-run as the service user.",
            file=sys.stderr,
        )
        return 4
    if not locked:
        print(
            "Error: the counter is in use by a running service. "
            "Stop it first (sudo systemctl stop solaredge-monitor).",
            file=sys.stderr,
        )
        return 3

    total = base + args.margin
    counter = CallCounter(path, billing_day=billing_day)
    try:
        new = counter.seed(total, force=args.force)
    except OSError as exc:
        print(f"Error: counter file {path} was NOT written ({exc})", file=sys.stderr)
        return 1
    print(f"Call counter: {new}/{HARD_LIMIT} in the current cycle (next reset {counter.next_reset()})")
    if new > total:
        print(f"Note: existing higher value kept (requested {total}); use --force to lower it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
