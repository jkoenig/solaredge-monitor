---
phase: 11-oauth-login-token-store
plan: 02
subsystem: auth
tags: [oauth, 1password, stdlib, scp, ssh]
requires: []
provides:
  - scripts/solaredge_login.py one-command Mac login (op -> browser -> callback -> exchange -> scp -> .env)
affects: [11-05]
tech-stack:
  added: []
  patterns: [stdlib-only script for macOS python 3.9, secrets via ssh stdin, atomic mv on Pi]
key-files:
  created: [scripts/solaredge_login.py, tests/test_login_script.py]
  modified: []
key-decisions:
  - "format_env_value single-quotes values containing $ to prevent dotenv interpolation"
  - "Remote .env merge drops duplicate keys, preserves comments/order, writes 0600 atomically"
requirements-completed: [AUTH-01, AUTH-02]
duration: 15min
completed: 2026-11-05
---

# Phase 11 Plan 02: Mac login script Summary

Stdlib-only `scripts/solaredge_login.py` implements the full D-17 flow (1Password creds, Pi .env secrets, browser consent with 127.0.0.1:8765 callback, immediate JSON code exchange, scp + chmod 600 + atomic mv of the token file, local cleanup, `--secrets-only`), with no refresh grant anywhere.

## Verification
- `/usr/bin/python3 -m unittest discover -s tests -p test_login_script.py`: 28 tests, OK (1 skipped: dotenv round-trip test, python-dotenv is absent from system python).
- `--help` lists --secrets-only, --host, --remote-dir, --op-item.
- Greps: no `0.0.0.0`, no refresh grant, compare_digest, mv -f, chmod 600, rmtree present.
- All I/O (op, ssh, scp, urlopen) was mocked; no real login, `op`, ssh or scp ran.

## Task commits
Both tasks (helpers and CLI flow) were written together and committed once: see git log, "feat(11-02): add Mac OAuth login script with tests".

## Deviations from Plan
- Tasks 1 and 2 committed as a single commit, since the files were authored together.
- The worktree base was corrected with `git reset --hard e2edb84` at startup per the base check.

## Known Stubs
None.

## Notes for 11-05
1Password field labels are unknown; if auto-detection fails the error lists labels, then use `--op-id-field` / `--op-secret-field`. The dotenv round-trip test runs only where python-dotenv is installed (e.g. the project venv).

## Self-Check: PASSED
