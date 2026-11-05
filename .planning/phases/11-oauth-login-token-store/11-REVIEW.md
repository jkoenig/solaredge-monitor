---
phase: 11-oauth-login-token-store
reviewed: 2026-11-05T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - config.py
  - main.py
  - screens/error.py
  - scripts/solaredge_login.py
  - token_store.py
  - tests/test_login_script.py
  - tests/test_main_login_state.py
  - tests/test_token_store.py
  - .gitignore
  - .env.example
findings:
  critical: 0
  warning: 4
  info: 5
  total: 9
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-11-05
**Depth:** standard
**Files Reviewed:** 10 (the three test files were not examined in depth; source files were read in full)

## Summary

The token store is sound on its main path. The refresh token is persisted with tmp, fsync and os.replace under flock before the new access token is used. Re-reading under the lock avoids double refresh. Secrets are not logged, and `TokenData.__repr__` hides the tokens. The Mac script sends the secrets to the Pi over stdin, not argv. The main-loop state machine has no stuck state. No critical issues were found. The weaknesses are all in robustness: the callback listener, a race between the Mac upload and the Pi refresh, and a gap in the rotation-loss handling.

## Warnings

### WR-01: Callback listener can hang on an idle connection

**File:** `scripts/solaredge_login.py:236-309`
**Issue:** `CallbackServer` is a single-threaded `HTTPServer`, and `_CallbackHandler` has no `timeout`. `server.timeout = 1` only bounds `select()` for new connections. Once `handle_request()` accepts a socket, it blocks in `rfile.readline()` with no limit. Chrome and Safari open speculative preconnect sockets that send nothing. If one of those is accepted before the real redirect, the listener stalls. The 300 s deadline is never re-checked, and the real callback queues behind the idle socket. A local process can also stall the login by opening a connection and sending nothing.
**Fix:**
```python
class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    timeout = 5  # per-connection socket timeout; the idle connection is dropped
```
Alternatively, use `ThreadingHTTPServer` with `daemon_threads = True`.

### WR-02: Callback without `state` is accepted, and any request to `/callback` ends the wait

**File:** `scripts/solaredge_login.py:85-102, 244-245`
**Issue:** The `state` check runs only when the callback carries `state` (D-02, deliberate). An attacker can still send `http://localhost:8765/callback?code=X&site_id=Y` with no `state`, for example from a web page that the browser then fetches. The state check is skipped. The code is sent to the token endpoint together with the user's client secret, and the resulting grant would be uploaded to the Pi. The code must be valid, so a forged code is unlikely to exchange, but this is login CSRF in principle. Separately, the handler stores the first `/callback` request as the result. A stray request such as `/callback?error=x` aborts the whole flow.
**Fix:** If the first real login shows that SolarEdge does echo `state`, require it (`expected_state is not None and "state" not in params` raises `CallbackError`). Otherwise, accept only a result that contains `code`, and keep listening for a bad or empty `/callback` until the deadline.

### WR-03: Token upload from the Mac races with a Pi refresh, with no lock

**File:** `scripts/solaredge_login.py:358-366`, `token_store.py:216-232`
**Issue:** The remote `mv -f temp final` does not take the Pi's `.tokens.json.lock`. Suppose the Pi has read the old token, is in the refresh HTTP call (up to 10 s), and the Mac `mv` lands in that window. The Pi's `save()` then replaces the freshly uploaded login with the rotated old chain. The new grant and its `granted_at` are lost. In the worst case the old chain is already dead, and the service falls back to "Login nötig". The window is narrow but real. It is easiest to hit when the old token has just expired.
**Fix:** Run the install under the same lock on the Pi. For example: `flock <final>.lock sh -c 'chmod 600 T && mv -f T F'`, with `flock(1)` quoted via `shlex`.

### WR-04: A failed persist after a successful refresh makes the old refresh token unusable

**File:** `token_store.py:294-298`
**Issue:** The server has already rotated the refresh token when the response arrives. If `save()` fails (disk full, read-only filesystem), the new pair is dropped and a `TransientAuthError` is raised. The next attempt then sends the old refresh token, which is probably invalidated. That gives 400, then `LoginRequired`. The code does its best, but the failure has no retry or fallback. For example, the new pair could be kept in memory and retried, or at least the log could say that a rotation was lost. `OSError` covers `mkstemp`, `write` and `replace`. A `JSONEncodeError` or `TypeError` from `to_dict` would not be caught.
**Fix:** Keep the unsaved `TokenData` in `self._pending` and try `save()` again at the start of the next `get_access_token()` before any refresh. Use that pair's refresh token. Also log "refresh token rotated but not persisted".

## Info

### IN-01: Non-dict JSON from the token endpoint crashes the login script with a traceback

**File:** `scripts/solaredge_login.py:105-108, 329-330`
**Issue:** `exchange_code` returns `json.loads(...)` unchecked. A list or string makes `token_response.get` raise `AttributeError`. `main()` catches only `LoginError`, so the user sees a traceback. `FileNotFoundError` for a missing `ssh` or `scp` binary behaves the same way. No secrets leak, but the error is ugly.
**Fix:** Check `isinstance(token_response, dict)` in `build_token_payload`. Also catch `OSError` in `_run`, or convert it to `LoginError`.

### IN-02: NaN or Infinity in the token file disables refreshing forever

**File:** `token_store.py:62-66, 208-209`
**Issue:** `json.loads` accepts `NaN` and `Infinity`, and `float()` accepts them. With `expires_at = NaN`, `NaN - now <= 300` is False, so `_needs_refresh` is never True. The same happens with `inf`. A hand-edited or corrupt file is accepted as valid.
**Fix:** In `_req_float`, add `if not math.isfinite(result): raise ValueError(...)`. Apply the same check to `expires_in` in `_refresh_locked`.

### IN-03: `.env` merge splits values on exotic line separators

**File:** `scripts/solaredge_login.py:184`
**Issue:** `format_env_value` rejects only `\n` and `\r`. The remote script uses `str.splitlines()`, which also splits on `\x0b`, `\x0c`, `\x1c-\x1e`, `\x85`, ` ` and ` `. A secret that contains one of these is silently truncated or corrupted in `.env`. Such characters are very unlikely in a client secret.
**Fix:** Use `sys.stdin.read().split("\n")`, or reject these characters in `format_env_value`.

### IN-04: `TokenStore` uses `requests.post` for the refresh but `self.session` for API calls

**File:** `token_store.py:238`
**Issue:** The refresh bypasses `self.session`, which the comment calls the deliberately plain no-retry session. This is inconsistent. The two paths take different connection and proxy configuration if the session is ever customised.
**Fix:** Use `self.session.post(...)`, and update the tests that patch `requests.post`.

### IN-05: Resuming after a deferred transient error keeps the old failure counter

**File:** `main.py:308-312`
**Issue:** The `TransientAuthError` branch sets `login_needed = False` but, unlike the success branch, does not reset `consecutive_failures`. A stale count can bring forward the error screen after login. Also, a `--host` argument that starts with `-` would be interpreted by `ssh` or `scp` as an option (`scripts/solaredge_login.py:358`). It is a local operator-only CLI, so the risk is negligible. Use `ssh -- host` if you want to harden it.
**Fix:** Add `consecutive_failures = 0` in the `TransientAuthError` branch.

---

_Reviewed: 2026-11-05_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
