"""Tests for token_store (stdlib unittest, runs on macOS and Pi)."""

import json
import os
import stat
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

import token_store  # noqa: E402
from token_store import (  # noqa: E402
    LoginRequired,
    TokenData,
    TokenFileWatcher,
    TokenStore,
    TransientAuthError,
)

OLD_ACCESS = "old-access-AAA"
OLD_REFRESH = "old-refresh-BBB"
NEW_ACCESS = "new-access-CCC"
NEW_REFRESH = "new-refresh-DDD"
SECRET = "super-secret-EEE"
NOW = 1_800_000_000.0


def make_data(expires_at=NOW + 3600, granted_at=NOW - 86400, access=OLD_ACCESS, refresh=OLD_REFRESH):
    return TokenData(
        access_token=access,
        refresh_token=refresh,
        token_type="Bearer",
        expires_at=expires_at,
        obtained_at=NOW - 100,
        granted_at=granted_at,
        site_id="12345",
    )


def fake_response(status=200, body=None, json_error=False):
    resp = mock.MagicMock()
    resp.status_code = status
    if json_error:
        resp.json.side_effect = ValueError("no json")
    else:
        resp.json.return_value = body if body is not None else {}
    return resp


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.path = self.dir / ".tokens.json"
        self.store = self.make_store()

    def make_store(self, client_id="cid", client_secret=SECRET, env_file=None):
        return TokenStore(self.path, client_id, client_secret, env_file)


class TokenFileTests(StoreTestCase):
    def test_load_missing(self):
        with self.assertRaises(LoginRequired) as cm:
            self.store.load()
        self.assertEqual(cm.exception.reason, "token file missing")

    def test_load_corrupt_variants(self):
        good = make_data().to_dict()
        bad_cases = [
            "{not json",
            json.dumps([1, 2]),
            json.dumps({k: v for k, v in good.items() if k != "refresh_token"}),
            json.dumps({**good, "access_token": ""}),
            json.dumps({**good, "expires_at": "soon"}),
        ]
        for text in bad_cases:
            self.path.write_text(text)
            with self.assertRaises(LoginRequired) as cm:
                self.store.load()
            self.assertEqual(cm.exception.reason, "token file corrupt", text)

    def test_load_valid_int_site_id(self):
        d = make_data().to_dict()
        d["site_id"] = 12345
        self.path.write_text(json.dumps(d))
        data = self.store.load()
        self.assertEqual(data.site_id, "12345")
        self.assertEqual(self.store.site_id, "12345")

    def test_save_roundtrip_mode_and_no_tmp(self):
        data = make_data()
        self.store.save(data)
        self.assertEqual(self.store.load(), data)
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        self.assertEqual([p.name for p in self.dir.glob("*.tmp")], [])

    def test_save_failure_keeps_old_file(self):
        self.store.save(make_data())
        before = self.path.read_bytes()
        with mock.patch("token_store.os.replace", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                self.store.save(make_data(access=NEW_ACCESS))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.store.load().access_token, OLD_ACCESS)
        self.assertEqual([p.name for p in self.dir.glob("*.tmp")], [])

    def test_lock_file_property(self):
        self.assertEqual(self.store.lock_file, self.dir / ".tokens.json.lock")

    def test_repr_hides_tokens(self):
        r = repr(make_data())
        self.assertNotIn(OLD_ACCESS, r)
        self.assertNotIn(OLD_REFRESH, r)

    def test_watcher(self):
        other = self.dir / ".env"
        self.store.save(make_data())
        w = TokenFileWatcher(self.path, other)
        w.reset()
        self.assertFalse(w.has_changed())
        tmp = self.dir / "new.tmp"
        tmp.write_text(json.dumps(make_data(access=NEW_ACCESS).to_dict()))
        os.replace(tmp, self.path)
        self.assertTrue(w.has_changed())
        self.assertFalse(w.has_changed())
        other.write_text("X=1")
        self.assertTrue(w.has_changed())
        self.assertFalse(w.has_changed())
        other.unlink()
        self.assertTrue(w.has_changed())
        self.assertFalse(w.has_changed())


class RefreshTests(StoreTestCase):
    def ok_body(self, **extra):
        body = {"access_token": NEW_ACCESS, "refresh_token": NEW_REFRESH, "expires_in": 7200, "token_type": "Bearer"}
        body.update(extra)
        return body

    def test_no_refresh_when_valid(self):
        self.store.save(make_data(expires_at=NOW + 301))
        with mock.patch("token_store.requests.post") as post:
            self.assertEqual(self.store.get_access_token(NOW), OLD_ACCESS)
        post.assert_not_called()

    def test_refresh_when_near_expiry(self):
        self.store.save(make_data(expires_at=NOW + 300))
        with mock.patch("token_store.requests.post", return_value=fake_response(200, self.ok_body())) as post:
            token = self.store.get_access_token(NOW)
        self.assertEqual(token, NEW_ACCESS)
        self.assertEqual(post.call_count, 1)
        args, kwargs = post.call_args
        self.assertEqual(args[0], token_store.TOKEN_URL)
        self.assertEqual(
            kwargs["json"],
            {"grant_type": "refresh_token", "refresh_token": OLD_REFRESH, "client_id": "cid", "client_secret": SECRET},
        )
        self.assertNotIn("data", kwargs)
        self.assertEqual(kwargs["timeout"], 10)
        saved = self.store.load()
        self.assertEqual(saved.access_token, NEW_ACCESS)
        self.assertEqual(saved.refresh_token, NEW_REFRESH)
        self.assertEqual(saved.expires_at, NOW + 7200)
        self.assertEqual(saved.obtained_at, NOW)
        self.assertEqual(saved.granted_at, NOW - 86400)
        self.assertEqual(saved.site_id, "12345")

    def test_missing_refresh_token_keeps_old(self):
        self.store.save(make_data(expires_at=NOW))
        body = self.ok_body()
        del body["refresh_token"]
        with mock.patch("token_store.requests.post", return_value=fake_response(200, body)):
            with self.assertLogs(level="WARNING"):
                self.assertEqual(self.store.get_access_token(NOW), NEW_ACCESS)
        self.assertEqual(self.store.load().refresh_token, OLD_REFRESH)

    def test_save_failure_not_returned(self):
        self.store.save(make_data(expires_at=NOW))
        with mock.patch("token_store.requests.post", return_value=fake_response(200, self.ok_body())):
            with mock.patch.object(TokenStore, "save", side_effect=OSError("disk full")):
                with self.assertRaises(TransientAuthError):
                    self.store.get_access_token(NOW)

    def test_rejected_raises_login_required(self):
        for code in (400, 401):
            self.store.save(make_data(expires_at=NOW))
            before = self.path.read_bytes()
            with mock.patch("token_store.requests.post", return_value=fake_response(code)) as post:
                with self.assertRaises(LoginRequired) as cm:
                    self.store.get_access_token(NOW)
            self.assertEqual(post.call_count, 1)
            self.assertEqual(cm.exception.reason, f"refresh rejected (HTTP {code})")
            self.assertEqual(self.path.read_bytes(), before)

    def test_transient_failures(self):
        failures = [
            {"side_effect": requests.exceptions.Timeout()},
            {"side_effect": requests.exceptions.ConnectionError()},
            {"return_value": fake_response(503)},
            {"return_value": fake_response(200, json_error=True)},
        ]
        for kw in failures:
            # token still valid (inside margin) -> old token returned
            self.store.save(make_data(expires_at=NOW + 100))
            before = self.path.read_bytes()
            with mock.patch("token_store.requests.post", **kw):
                self.assertEqual(self.store.get_access_token(NOW), OLD_ACCESS)
            self.assertEqual(self.path.read_bytes(), before)
            # token expired -> TransientAuthError
            self.store.save(make_data(expires_at=NOW - 1))
            before = self.path.read_bytes()
            with mock.patch("token_store.requests.post", **kw):
                with self.assertRaises(TransientAuthError):
                    self.store.get_access_token(NOW)
            self.assertEqual(self.path.read_bytes(), before)

    def test_missing_client_credentials(self):
        store = self.make_store(client_id="", client_secret="")
        store.save(make_data(expires_at=NOW))
        with mock.patch("token_store.requests.post") as post:
            with self.assertRaises(LoginRequired) as cm:
                store.get_access_token(NOW)
        self.assertEqual(cm.exception.reason, "client credentials missing")
        post.assert_not_called()

    def test_lock_race_single_post(self):
        store_a = self.make_store()
        store_b = self.make_store()
        store_a.save(make_data(expires_at=NOW))
        result = {}
        started = threading.Event()

        def worker():
            started.set()
            with mock.patch("token_store.requests.post") as post:
                try:
                    result["token"] = store_b.get_access_token(NOW)
                except Exception as exc:  # pragma: no cover
                    result["error"] = exc
                result["posts"] = post.call_count

        with store_a._locked():
            t = threading.Thread(target=worker)
            t.start()
            self.assertTrue(started.wait(5))
            time.sleep(0.3)
            self.assertTrue(t.is_alive(), "second refresher should block on the lock")
            store_a.save(make_data(expires_at=NOW + 7200, access=NEW_ACCESS, refresh=NEW_REFRESH))
        t.join(5)
        self.assertFalse(t.is_alive())
        self.assertNotIn("error", result)
        self.assertEqual(result["token"], NEW_ACCESS)
        self.assertEqual(result["posts"], 0)

    def test_force_refresh(self):
        self.store.save(make_data(expires_at=NOW + 7200, access=NEW_ACCESS))
        with mock.patch("token_store.requests.post") as post:
            self.assertEqual(self.store.force_refresh(OLD_ACCESS, NOW), NEW_ACCESS)
        post.assert_not_called()
        body = self.ok_body(access_token="forced-FFF")
        with mock.patch("token_store.requests.post", return_value=fake_response(200, body)) as post:
            self.assertEqual(self.store.force_refresh(NEW_ACCESS, NOW), "forced-FFF")
        self.assertEqual(post.call_count, 1)

    def test_force_refresh_transient_raises(self):
        self.store.save(make_data(expires_at=NOW + 7200))
        with mock.patch("token_store.requests.post", side_effect=requests.exceptions.Timeout()):
            with self.assertRaises(TransientAuthError):
                self.store.force_refresh(OLD_ACCESS, NOW)

    def test_authorized_request(self):
        self.store.save(make_data(expires_at=time.time() + 7200))
        r401, r200 = mock.MagicMock(status_code=401), mock.MagicMock(status_code=200)
        with mock.patch.object(self.store.session, "request", side_effect=[r401, r200]) as req:
            with mock.patch("token_store.requests.post", return_value=fake_response(200, self.ok_body())):
                with self.assertLogs(level="WARNING"):
                    resp = self.store.authorized_request("GET", "https://x.example/api")
        self.assertIs(resp, r200)
        self.assertEqual(req.call_args_list[0].kwargs["headers"]["Authorization"], f"Bearer {OLD_ACCESS}")
        self.assertEqual(req.call_args_list[1].kwargs["headers"]["Authorization"], f"Bearer {NEW_ACCESS}")

    def test_authorized_request_double_401(self):
        self.store.save(make_data(expires_at=time.time() + 7200))
        r401 = mock.MagicMock(status_code=401)
        with mock.patch.object(self.store.session, "request", side_effect=[r401, r401]):
            with mock.patch("token_store.requests.post", return_value=fake_response(200, self.ok_body())):
                with self.assertRaises(LoginRequired) as cm:
                    self.store.authorized_request("GET", "https://x.example/api")
        self.assertEqual(cm.exception.reason, "API rejected token after refresh")

    def test_reload_credentials(self):
        env = self.dir / ".env"
        env.write_text("SOLAREDGE_CLIENT_ID=new_id\nSOLAREDGE_CLIENT_SECRET=new_secret\n")
        store = self.make_store(env_file=env)
        store.reload_credentials()
        self.assertEqual((store.client_id, store.client_secret), ("new_id", "new_secret"))
        store2 = self.make_store(env_file=self.dir / "nope.env")
        store2.reload_credentials()
        self.assertEqual((store2.client_id, store2.client_secret), ("cid", SECRET))

    def test_grant_warning(self):
        self.store.save(make_data(granted_at=NOW - 710 * 86400))
        with self.assertLogs(level="WARNING") as cm:
            self.store.warn_if_grant_expiring(NOW)
        self.assertEqual(len(cm.records), 1)
        with self.assertNoLogs(level="WARNING"):
            self.store.warn_if_grant_expiring(NOW)

    def test_grant_no_warning_when_far(self):
        self.store.save(make_data(granted_at=NOW - 100 * 86400))
        with self.assertNoLogs(level="WARNING"):
            self.store.warn_if_grant_expiring(NOW)

    def test_secret_hygiene(self):
        secrets = [OLD_ACCESS, OLD_REFRESH, NEW_ACCESS, NEW_REFRESH, SECRET]
        scenarios = [
            fake_response(200, self.ok_body()),
            fake_response(400),
            requests.exceptions.Timeout(f"timeout {SECRET}"),
        ]
        for sc in scenarios:
            self.store.save(make_data(expires_at=NOW))
            kw = {"side_effect": sc} if isinstance(sc, Exception) else {"return_value": sc}
            with self.assertLogs(level="DEBUG") as cm:
                import logging

                logging.debug("sentinel")
                with mock.patch("token_store.requests.post", **kw):
                    try:
                        self.store.get_access_token(NOW)
                    except (LoginRequired, TransientAuthError):
                        pass
            for rec in cm.records:
                msg = rec.getMessage()
                for s in secrets:
                    self.assertNotIn(s, msg)


if __name__ == "__main__":
    unittest.main()
