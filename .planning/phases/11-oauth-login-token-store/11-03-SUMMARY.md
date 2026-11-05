---
phase: 11-oauth-login-token-store
plan: 03
subsystem: display-config
tags: [oauth, eink, config, gitignore]
requires: []
provides:
  - "screens.error.render_login_required_screen()"
  - "Config.client_id, client_secret, token_file, env_file; optional site_id"
affects: [11-04]
key-files:
  modified: [screens/error.py, config.py, .gitignore, .env.example]
decisions:
  - "Token file defaults to <app dir>/.tokens.json, override via SOLAREDGE_TOKEN_FILE"
metrics:
  tasks: 2
  completed: 2026-11-05
---

# Phase 11 Plan 03: Login screen and OAuth config Summary

"Login nötig" e-ink screen via a shared headline+message helper, plus Config fields for OAuth client credentials and token file path, with token files git-ignored.

## Tasks

1. Login screen (commit 4307399): `_render_headline_message` extracted; `render_error_screen` hashes are identical before and after (verified against baseline). `render_login_required_screen()` renders 1000x488 mode '1'; hint fits on one line, wrap safeguard after "Mac:" included. Not added to `get_screens()`.
2. Config (commit cbd0a65): SOLAREDGE_SITE_ID no longer required (D-14), API key still required (D-15); client id/secret loaded without validation errors; `log_startup` logs secret only as set/missing and the client id masked; `.gitignore` covers `.tokens.json` and `.tokens.json.*`; `.env.example` updated.

## Deviations from Plan

None in substance. Verification commands using `env -i` were blocked by the sandbox, so the environment-isolated checks were run via a scratchpad Python script that clears SOLAREDGE_* variables in-process; the same assertions passed (missing API key raises ValueError without mentioning SITE_ID; secret absent from log output).

## Known Stubs

None.

## Self-Check: PASSED
