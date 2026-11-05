"""OAuth token store for the SolarEdge V2 API.

Only the Pi refreshes tokens (the Mac login script performs the initial
login and uploads the token file, then keeps no copy). The rotated token
pair is persisted atomically under an flock before the new access token is
ever used, so a crash or a second process can never lose the refresh chain.

Token file format (JSON, version 1, mode 0600):
    version, access_token, refresh_token, token_type, expires_at (UTC epoch),
    obtained_at (UTC epoch), granted_at (UTC epoch of browser consent),
    site_id.

Secrets (tokens, client secret, response bodies) are never logged.
"""

import contextlib
import fcntl
import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Union
from zoneinfo import ZoneInfo

import requests

TOKEN_URL = "https://monitoringapi.solaredge.com/v2/oauth2/token"
REFRESH_MARGIN_SECONDS = 300
GRANT_MONTHS = 24
GRANT_WARN_DAYS = 30
HTTP_TIMEOUT = 10
FILE_VERSION = 1


class LoginRequired(Exception):
    """The token state is unusable; the owner must run the login script."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class TransientAuthError(Exception):
    """Token refresh failed temporarily; this does not mean re-login."""


def _req_str(d: dict, key: str) -> str:
    value = d.get(key)
    if isinstance(value, bool):
        raise ValueError(f"{key} invalid")
    if isinstance(value, int) and key == "site_id":
        value = str(value)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _req_float(d: dict, key: str) -> float:
    value = d.get(key)
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{key} invalid")
    return float(value)


@dataclass(frozen=True)
class TokenData:
    """Persisted OAuth token pair.

    Fields:
        access_token: Bearer token (never shown in repr)
        refresh_token: Rotating refresh token (never shown in repr)
        token_type: Token type, normally "Bearer"
        expires_at: Absolute UTC epoch seconds when the access token expires
        obtained_at: UTC epoch seconds when this pair was obtained
        granted_at: UTC epoch seconds of the browser consent (24-month grant)
        site_id: SolarEdge site id as string
    """

    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    token_type: str
    expires_at: float
    obtained_at: float
    granted_at: float
    site_id: str

    @classmethod
    def from_dict(cls, d: dict) -> "TokenData":
        if not isinstance(d, dict):
            raise ValueError("token data must be an object")
        token_type = d.get("token_type", "Bearer")
        if not isinstance(token_type, str) or not token_type:
            raise ValueError("token_type invalid")
        return cls(
            access_token=_req_str(d, "access_token"),
            refresh_token=_req_str(d, "refresh_token"),
            token_type=token_type,
            expires_at=_req_float(d, "expires_at"),
            obtained_at=_req_float(d, "obtained_at"),
            granted_at=_req_float(d, "granted_at"),
            site_id=_req_str(d, "site_id"),
        )

    def to_dict(self) -> dict:
        return {
            "version": FILE_VERSION,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_at": self.expires_at,
            "obtained_at": self.obtained_at,
            "granted_at": self.granted_at,
            "site_id": self.site_id,
        }


class TokenStore:
    """Loads, refreshes and persists the OAuth token pair."""

    def __init__(
        self,
        token_file: Union[str, Path],
        client_id: str,
        client_secret: str,
        env_file: Optional[Union[str, Path]] = None,
    ):
        self.token_file = Path(token_file)
        self.client_id = client_id
        self.client_secret = client_secret
        self.env_file = Path(env_file) if env_file else None
        # Plain session, deliberately no retry adapter (D-05)
        self.session = requests.Session()
        self._last_grant_warning_date = None

    @property
    def lock_file(self) -> Path:
        return self.token_file.parent / (self.token_file.name + ".lock")

    # ---- file layer ----

    def load(self) -> TokenData:
        try:
            with open(self.token_file, "r", encoding="utf-8") as f:
                raw = f.read()
        except FileNotFoundError:
            raise LoginRequired("token file missing") from None
        except OSError:
            raise LoginRequired("token file unreadable") from None
        try:
            return TokenData.from_dict(json.loads(raw))
        except (ValueError, TypeError):
            # json.JSONDecodeError is a ValueError
            raise LoginRequired("token file corrupt") from None

    def save(self, data: TokenData) -> None:
        directory = self.token_file.parent
        fd, tmp = tempfile.mkstemp(
            dir=directory, prefix=self.token_file.name + ".", suffix=".tmp"
        )
        try:
            try:
                os.fchmod(fd, 0o600)
                payload = json.dumps(data.to_dict(), indent=2).encode("utf-8")
                view = memoryview(payload)
                while view:
                    written = os.write(fd, view)
                    view = view[written:]
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(tmp, self.token_file)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp)
            raise
        try:
            dfd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass  # some filesystems reject directory fsync

    @contextlib.contextmanager
    def _locked(self):
        fd = os.open(self.lock_file, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    @property
    def site_id(self) -> str:
        return self.load().site_id

    # ---- refresh ----

    @staticmethod
    def _needs_refresh(data: TokenData, now: float) -> bool:
        return data.expires_at - now <= REFRESH_MARGIN_SECONDS

    def get_access_token(self, now: Optional[float] = None) -> str:
        now = time.time() if now is None else now
        data = self.load()
        if not self._needs_refresh(data, now):
            return data.access_token
        with self._locked():
            # Another process may have refreshed while we waited for the lock
            data = self.load()
            if not self._needs_refresh(data, now):
                return data.access_token
            return self._refresh_locked(data, now)

    def force_refresh(self, rejected_access_token: str, now: Optional[float] = None) -> str:
        now = time.time() if now is None else now
        with self._locked():
            data = self.load()
            if data.access_token != rejected_access_token:
                return data.access_token
            return self._refresh_locked(data, now, allow_stale=False)

    def _refresh_locked(self, data: TokenData, now: float, allow_stale: bool = True) -> str:
        if not self.client_id or not self.client_secret:
            raise LoginRequired("client credentials missing")

        reason = None
        body = None
        try:
            resp = requests.post(
                TOKEN_URL,
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": data.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=HTTP_TIMEOUT,
            )
        except requests.exceptions.Timeout:
            reason = "timeout"
        except requests.exceptions.RequestException as exc:
            reason = f"network error ({type(exc).__name__})"
        else:
            code = resp.status_code
            if code in (400, 401):
                logging.error(f"Token refresh rejected (HTTP {code}); new login required")
                raise LoginRequired(f"refresh rejected (HTTP {code})")
            if code != 200:
                reason = f"HTTP {code}"
            else:
                try:
                    body = resp.json()
                except ValueError:
                    reason = "invalid response"
                if body is not None and (
                    not isinstance(body, dict)
                    or not isinstance(body.get("access_token"), str)
                    or not body.get("access_token")
                ):
                    reason = "invalid response"

        if reason is not None:
            logging.warning(f"Token refresh failed temporarily: {reason}")
            if allow_stale and now < data.expires_at:
                return data.access_token
            raise TransientAuthError(reason)

        new_refresh = body.get("refresh_token")
        if not isinstance(new_refresh, str) or not new_refresh:
            logging.warning("Token response contained no refresh token; keeping previous one")
            new_refresh = data.refresh_token
        try:
            expires_in = float(body.get("expires_in", 7200))
        except (TypeError, ValueError):
            expires_in = 7200.0
        new = TokenData(
            access_token=body["access_token"],
            refresh_token=new_refresh,
            token_type=body.get("token_type") or "Bearer",
            expires_at=now + expires_in,
            obtained_at=now,
            granted_at=data.granted_at,
            site_id=data.site_id,
        )
        try:
            self.save(new)  # persist before use (D-04)
        except OSError:
            logging.error("Failed to persist refreshed tokens")
            raise TransientAuthError("could not persist refreshed tokens") from None
        logging.info(f"Access token refreshed, expires in {int(expires_in // 60)} min")
        return new.access_token

    # ---- authorized requests ----

    def authorized_request(self, method: str, url: str, **kwargs) -> requests.Response:
        token = self.get_access_token()
        headers = dict(kwargs.pop("headers", {}) or {})
        kwargs.setdefault("timeout", HTTP_TIMEOUT)
        headers["Authorization"] = f"Bearer {token}"
        resp = self.session.request(method, url, headers=headers, **kwargs)
        if resp.status_code == 401:
            logging.warning("API returned 401, refreshing token once")
            token = self.force_refresh(token)
            retry_headers = {**headers, "Authorization": f"Bearer {token}"}
            resp = self.session.request(method, url, headers=retry_headers, **kwargs)
            if resp.status_code == 401:
                raise LoginRequired("API rejected token after refresh")
        return resp

    # ---- credentials & grant expiry ----

    def reload_credentials(self) -> None:
        if not self.env_file or not self.env_file.exists():
            return
        from dotenv import dotenv_values

        values = dotenv_values(self.env_file, interpolate=False)
        cid = values.get("SOLAREDGE_CLIENT_ID")
        secret = values.get("SOLAREDGE_CLIENT_SECRET")
        if cid:
            self.client_id = cid
        if secret:
            self.client_secret = secret
        logging.info("Client credentials reloaded from .env")

    def warn_if_grant_expiring(self, now: Optional[float] = None) -> None:
        try:
            data = self.load()
        except LoginRequired:
            return
        granted = datetime.fromtimestamp(data.granted_at, tz=timezone.utc)
        try:
            expiry = granted.replace(year=granted.year + GRANT_MONTHS // 12)
        except ValueError:  # Feb 29
            expiry = granted.replace(year=granted.year + GRANT_MONTHS // 12, day=28)
        warn_from = expiry - timedelta(days=GRANT_WARN_DAYS)
        tz = ZoneInfo("Europe/Berlin")
        if now is None:
            now = time.time()
        today = datetime.fromtimestamp(now, tz=tz).date()
        if now >= warn_from.timestamp() and self._last_grant_warning_date != today:
            logging.warning(
                f"SolarEdge grant expires on {expiry:%Y-%m-%d}; run the Mac login script before then"
            )
            self._last_grant_warning_date = today


class TokenFileWatcher:
    """Detects new/changed/removed files (token file, .env)."""

    def __init__(self, *paths: Union[str, Path]):
        self.paths = [Path(p) for p in paths]
        self._baseline = self._snapshot()

    def _snapshot(self) -> list:
        snap = []
        for p in self.paths:
            try:
                st = os.stat(p)
                snap.append((st.st_ino, st.st_mtime_ns, st.st_size))
            except OSError:
                snap.append(None)
        return snap

    def reset(self) -> None:
        self._baseline = self._snapshot()

    def has_changed(self) -> bool:
        current = self._snapshot()
        changed = current != self._baseline
        self._baseline = current
        return changed
