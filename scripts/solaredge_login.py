#!/usr/bin/env python3
"""One-command SolarEdge OAuth login, run on the Mac.

Flow (D-17):
  1. read the OAuth client id/secret from 1Password (`op`, never printed)
  2. write SOLAREDGE_CLIENT_ID / SOLAREDGE_CLIENT_SECRET into the Pi's .env
  3. open the SolarEdge consent page in the browser, listen on
     127.0.0.1:8765/callback for the redirect
  4. exchange the authorization code immediately for tokens
  5. upload the token file to se-monitor (scp to a temp name, chmod 600,
     atomic mv) and delete every local copy

The Mac never refreshes tokens (D-01): the Pi owns the refresh chain.
A refresh on this machine would invalidate the Pi's refresh token.

Usage:
  python3 scripts/solaredge_login.py                 # full login
  python3 scripts/solaredge_login.py --secrets-only  # only update Pi .env

Stdlib only, compatible with macOS system python3 (3.9) (D-18).
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

AUTHORIZE_URL = "https://connect.solaredge.com/authorize"
TOKEN_URL = "https://monitoringapi.solaredge.com/v2/oauth2/token"
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 8765
REDIRECT_URI = "http://localhost:8765/callback"
SCOPE = "SITE_DATA DEVICE_DATA"
ACCESS_DURATION = "24"
OP_ITEM = "7rboxat3in2tlx2ywilmsna5cy"
# The item lives in the personal 1Password account, not the default (work) one.
OP_ACCOUNT = "my.1password.com"
DEFAULT_HOST = "se-monitor"
DEFAULT_REMOTE_DIR = "/home/pi/solaredge-monitor"
TOKEN_FILENAME = ".tokens.json"
CALLBACK_TIMEOUT_SECONDS = 300
GRANT_MONTHS = 24


class LoginError(Exception):
    """Fatal problem during the login flow."""


class CallbackError(LoginError):
    """The OAuth redirect was invalid or reported an error."""


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def build_authorize_url(client_id: str, state: str) -> str:
    query = urllib.parse.urlencode(
        [
            ("client_id", client_id),
            ("redirect_uri", REDIRECT_URI),
            ("scope", SCOPE),
            ("state", state),
            ("access_duration", ACCESS_DURATION),
        ],
        quote_via=urllib.parse.quote,
    )
    return AUTHORIZE_URL + "?" + query


def validate_callback(
    params: Dict[str, List[str]], expected_state: Optional[str]
) -> Tuple[str, str]:
    """Return (code, site_id) or raise CallbackError. State checked only if present."""
    if "error" in params:
        raise CallbackError("Authorization failed: " + params["error"][0])
    if "state" in params and expected_state is not None:
        if not secrets.compare_digest(
            params["state"][0].encode("utf-8"), expected_state.encode("utf-8")
        ):
            raise CallbackError("State mismatch in callback")
    code = (params.get("code") or [""])[0]
    site_id = (params.get("site_id") or [""])[0]
    if not code:
        raise CallbackError("Callback is missing 'code'")
    if not site_id:
        raise CallbackError("Callback is missing 'site_id'")
    return code, site_id


def build_token_payload(token_response: dict, site_id: str, now: float) -> dict:
    access = token_response.get("access_token")
    refresh = token_response.get("refresh_token")
    if not access or not refresh:
        raise LoginError("Token response lacks access_token or refresh_token")
    try:
        expires_in = float(token_response.get("expires_in", 0))
    except (TypeError, ValueError):
        raise LoginError("Token response has invalid expires_in")
    return {
        "version": 1,
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "Bearer",
        "expires_at": now + expires_in,
        "obtained_at": now,
        "granted_at": now,
        "site_id": str(site_id),
    }


def _norm_label(label: str) -> str:
    return "".join(ch for ch in label.lower() if ch not in " _-")


_ID_LABELS = ("clientid", "username")
_SECRET_LABELS = ("clientsecret", "password", "credential")


def pick_op_fields(
    item: dict, id_label: Optional[str] = None, secret_label: Optional[str] = None
) -> Tuple[str, str]:
    fields = item.get("fields") or []
    by_label = {}
    for f in fields:
        label = f.get("label")
        value = f.get("value")
        if label and value:
            by_label.setdefault(_norm_label(label), value)

    def find(override: Optional[str], candidates: Tuple[str, ...]) -> Optional[str]:
        if override:
            return by_label.get(_norm_label(override))
        for cand in candidates:
            if cand in by_label:
                return by_label[cand]
        return None

    client_id = find(id_label, _ID_LABELS)
    client_secret = find(secret_label, _SECRET_LABELS)
    if not client_id or not client_secret:
        labels = sorted(f.get("label", "?") for f in fields if f.get("label"))
        raise LoginError(
            "Could not find client id/secret in 1Password item. "
            "Available field labels: " + ", ".join(labels)
            + " (use --op-id-field / --op-secret-field)"
        )
    return client_id, client_secret


def format_env_value(value: str) -> str:
    """Format a value for a .env line so python-dotenv reads it back unchanged."""
    if "\n" in value or "\r" in value:
        raise LoginError("Value contains a newline and cannot be stored in .env")
    if "$" in value:
        # single-quote values with "$"; readers also load .env with interpolate=False
        # (python-dotenv expands ${...} even inside single quotes otherwise)
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        return "'" + escaped + "'"
    if any(ch in value for ch in " #\"'\\\t"):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return '"' + escaped + '"'
    return value


REMOTE_ENV_MERGE = r'''
import os, sys, tempfile
path = sys.argv[1]
updates = []
for raw in sys.stdin.read().splitlines():
    if "=" in raw:
        updates.append((raw.split("=", 1)[0].strip(), raw))
try:
    with open(path, "r") as fh:
        lines = fh.read().split("\n")
except FileNotFoundError:
    lines = []
if lines and lines[-1] == "":
    lines.pop()

def key_of(line):
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        return None
    if s.startswith("export "):
        s = s[7:]
    return s.split("=", 1)[0].strip()

for key, new_line in updates:
    out, done = [], False
    for line in lines:
        if key_of(line) == key:
            if not done:
                out.append(new_line)
                done = True
            continue
        out.append(line)
    if not done:
        out.append(new_line)
    lines = out

directory = os.path.dirname(os.path.abspath(path))
fd, tmp = tempfile.mkstemp(dir=directory, prefix=".env.")
try:
    with os.fdopen(fd, "w") as fh:
        fh.write("\n".join(lines) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
except BaseException:
    if os.path.exists(tmp):
        os.unlink(tmp)
    raise
'''


# ---------------------------------------------------------------------------
# Callback server (loopback only)
# ---------------------------------------------------------------------------

class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        self.server.result = params  # type: ignore[attr-defined]
        if "error" in params:
            text = "Login fehlgeschlagen: " + params["error"][0]
        else:
            text = "Login erfolgreich – Fenster kann geschlossen werden."
        body = (
            "<!doctype html><html><head><meta charset='utf-8'></head>"
            "<body><p>" + text.replace("<", "&lt;") + "</p></body></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        # query string carries the one-use code: never log it
        return


class CallbackServer(http.server.HTTPServer):
    def __init__(self, port: int = CALLBACK_PORT) -> None:
        self.result: Optional[Dict[str, List[str]]] = None
        super().__init__((CALLBACK_HOST, port), _CallbackHandler)


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def read_op_credentials(
    item: str, id_label: Optional[str], secret_label: Optional[str],
    account: Optional[str] = OP_ACCOUNT,
) -> Tuple[str, str]:
    if shutil.which("op") is None:
        raise LoginError(
            "1Password CLI `op` not found. Install it and sign in (op signin)."
        )
    cmd = ["op", "item", "get", item, "--format", "json"]
    if account:
        cmd += ["--account", account]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        first = (proc.stderr or "").strip().splitlines()[:1]
        raise LoginError("op failed: " + (first[0] if first else "unknown error"))
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        raise LoginError("op returned invalid JSON")
    return pick_op_fields(data, id_label, secret_label)


def wait_for_callback(server: CallbackServer, timeout: float) -> Dict[str, List[str]]:
    server.timeout = 1
    deadline = time.time() + timeout
    while server.result is None:
        if time.time() > deadline:
            raise LoginError("No callback within %d s" % int(timeout))
        server.handle_request()
    return server.result


def exchange_code(code: str, client_id: str, client_secret: str) -> dict:
    body = json.dumps(
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            parsed = json.loads(e.read().decode("utf-8"))
            err = parsed.get("error") if isinstance(parsed, dict) else None
            if isinstance(err, str):
                detail = " " + err
        except Exception:
            pass
        raise LoginError("Token exchange failed: HTTP %s%s" % (e.code, detail))
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise LoginError("Token exchange failed: %s" % type(e).__name__)


def _run(args: List[str], **kwargs) -> "subprocess.CompletedProcess":
    return subprocess.run(args, check=False, **kwargs)


def upload_token_file(payload: dict, host: str, remote_dir: str) -> None:
    tmpdir = tempfile.mkdtemp(prefix="solaredge-login-")
    try:
        local = os.path.join(tmpdir, TOKEN_FILENAME)
        fd = os.open(local, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump(payload, fh)
        final = remote_dir.rstrip("/") + "/" + TOKEN_FILENAME
        temp = final + ".upload"
        r = _run(["scp", "-q", local, "%s:%s" % (host, temp)])
        if r.returncode != 0:
            raise LoginError("scp to %s failed" % host)
        cmd = "umask 077 && chmod 600 %s && mv -f %s %s" % (
            shlex.quote(temp), shlex.quote(temp), shlex.quote(final),
        )
        r = _run(["ssh", host, cmd])
        if r.returncode != 0:
            raise LoginError("Installing token file on %s failed" % host)
        r = _run(
            ["ssh", host, "stat -c %%a %s" % shlex.quote(final)],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0 or (r.stdout or "").strip() != "600":
            raise LoginError("Token file on %s does not have mode 600" % host)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def update_remote_env(
    host: str, remote_dir: str, client_id: str, client_secret: str
) -> None:
    env_path = remote_dir.rstrip("/") + "/.env"
    stdin = (
        "SOLAREDGE_CLIENT_ID=" + format_env_value(client_id) + "\n"
        "SOLAREDGE_CLIENT_SECRET=" + format_env_value(client_secret) + "\n"
    )
    remote = "python3 -c %s %s" % (shlex.quote(REMOTE_ENV_MERGE), shlex.quote(env_path))
    r = _run(["ssh", host, remote], input=stdin, text=True)
    if r.returncode != 0:
        raise LoginError("Updating .env on %s failed" % host)


def cleanup_local_copies() -> None:
    local = Path(__file__).resolve().parent.parent / TOKEN_FILENAME
    if local.exists():
        local.unlink()
        print("Removed local %s." % local)


def _mask(site_id: str) -> str:
    return "..." + site_id[-4:] if len(site_id) > 4 else site_id


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="SolarEdge OAuth login for se-monitor")
    ap.add_argument("--secrets-only", action="store_true",
                    help="only update client id/secret in the Pi .env, no login")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--remote-dir", default=DEFAULT_REMOTE_DIR)
    ap.add_argument("--op-item", default=OP_ITEM)
    ap.add_argument("--op-account", default=OP_ACCOUNT,
                    help="1Password account (sign-in address); empty string = op default")
    ap.add_argument("--op-id-field", default=None)
    ap.add_argument("--op-secret-field", default=None)
    ap.add_argument("--port", type=int, default=CALLBACK_PORT,
                    help="listener port (tests only: the redirect URI stays fixed "
                         "on 8765, another port would not receive the redirect)")
    args = ap.parse_args(argv)

    try:
        client_id, client_secret = read_op_credentials(
            args.op_item, args.op_id_field, args.op_secret_field,
            args.op_account or None,
        )
        update_remote_env(args.host, args.remote_dir, client_id, client_secret)
        print("Client credentials written to %s:%s/.env" % (args.host, args.remote_dir))
        if args.secrets_only:
            print("Done (--secrets-only).")
            return 0

        state = secrets.token_urlsafe(24)
        try:
            server = CallbackServer(args.port)
        except OSError as e:
            raise LoginError(
                "Cannot listen on %s:%d (%s). Is another login running?"
                % (CALLBACK_HOST, args.port, e.strerror or e)
            )
        try:
            url = build_authorize_url(client_id, state)
            print("Opening browser for consent. If nothing opens, visit:\n  " + url)
            webbrowser.open(url)
            params = wait_for_callback(server, CALLBACK_TIMEOUT_SECONDS)
        finally:
            server.server_close()
        code, site_id = validate_callback(params, state)
        tokens = exchange_code(code, client_id, client_secret)
        now = time.time()
        payload = build_token_payload(tokens, site_id, now)
        upload_token_file(payload, args.host, args.remote_dir)
        cleanup_local_copies()
        print("Site: %s" % _mask(site_id))
        print("Access token valid until: %s"
              % time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(payload["expires_at"])))
        print("Grant valid for about %d months." % GRANT_MONTHS)
        print("The Pi now refreshes the tokens; this Mac keeps no copy.")
        return 0
    except LoginError as e:
        print("Fehler: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
