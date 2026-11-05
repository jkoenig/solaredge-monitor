"""Tests for scripts/solaredge_login.py (stdlib unittest, python 3.9 compatible)."""
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import solaredge_login as sl  # noqa: E402

try:
    from dotenv import dotenv_values
except ImportError:  # system python has no python-dotenv
    dotenv_values = None


class PureHelpers(unittest.TestCase):
    def test_authorize_url(self):
        self.assertEqual(
            sl.build_authorize_url("cid", "abc"),
            "https://connect.solaredge.com/authorize?client_id=cid"
            "&redirect_uri=http%3A%2F%2Flocalhost%3A8765%2Fcallback"
            "&scope=SITE_DATA%20DEVICE_DATA&state=abc&access_duration=24",
        )

    def test_validate_callback_ok_without_state(self):
        self.assertEqual(
            sl.validate_callback({"code": ["c"], "site_id": ["42"]}, "s"), ("c", "42"))

    def test_validate_callback_state_match(self):
        p = {"code": ["c"], "site_id": ["42"], "state": ["s"]}
        self.assertEqual(sl.validate_callback(p, "s"), ("c", "42"))

    def test_validate_callback_state_mismatch(self):
        p = {"code": ["c"], "site_id": ["42"], "state": ["x"]}
        with self.assertRaises(sl.CallbackError):
            sl.validate_callback(p, "s")

    def test_validate_callback_error_param(self):
        with self.assertRaises(sl.CallbackError) as cm:
            sl.validate_callback({"error": ["access_denied"]}, "s")
        self.assertIn("access_denied", str(cm.exception))

    def test_validate_callback_missing(self):
        with self.assertRaises(sl.CallbackError):
            sl.validate_callback({"site_id": ["42"]}, "s")
        with self.assertRaises(sl.CallbackError):
            sl.validate_callback({"code": ["c"]}, "s")

    def test_token_payload(self):
        p = sl.build_token_payload(
            {"access_token": "a", "refresh_token": "r", "expires_in": 7200}, "42", 1000.0)
        self.assertEqual(p, {
            "version": 1, "access_token": "a", "refresh_token": "r",
            "token_type": "Bearer", "expires_at": 8200.0, "obtained_at": 1000.0,
            "granted_at": 1000.0, "site_id": "42"})

    def test_token_payload_missing_tokens(self):
        with self.assertRaises(sl.LoginError):
            sl.build_token_payload({"refresh_token": "r", "expires_in": 1}, "1", 0.0)
        with self.assertRaises(sl.LoginError):
            sl.build_token_payload({"access_token": "a", "expires_in": 1}, "1", 0.0)

    def test_pick_op_fields_labels(self):
        item = {"fields": [{"label": "Client ID", "value": "ID"},
                           {"label": "client_secret", "value": "SEC"}]}
        self.assertEqual(sl.pick_op_fields(item), ("ID", "SEC"))
        item = {"fields": [{"label": "username", "value": "u"},
                           {"label": "password", "value": "p"}]}
        self.assertEqual(sl.pick_op_fields(item), ("u", "p"))

    def test_pick_op_fields_override(self):
        item = {"fields": [{"label": "username", "value": "u"},
                           {"label": "my-id", "value": "mine"},
                           {"label": "password", "value": "p"}]}
        self.assertEqual(sl.pick_op_fields(item, "my id", None), ("mine", "p"))

    def test_pick_op_fields_missing_lists_labels_not_values(self):
        item = {"fields": [{"label": "foo", "value": "TOPSECRET"}]}
        with self.assertRaises(sl.LoginError) as cm:
            sl.pick_op_fields(item)
        self.assertIn("foo", str(cm.exception))
        self.assertNotIn("TOPSECRET", str(cm.exception))

    def test_format_env_value(self):
        self.assertEqual(sl.format_env_value("abc123"), "abc123")
        self.assertEqual(sl.format_env_value("a b"), '"a b"')
        self.assertEqual(sl.format_env_value('a#"b\\'), '"a#\\"b\\\\"')
        with self.assertRaises(sl.LoginError):
            sl.format_env_value("a\nb")

    @unittest.skipIf(dotenv_values is None, "python-dotenv not installed")
    def test_format_env_value_dotenv_roundtrip(self):
        for secret in ["${X}", "a$b'c", "p w#d", 'q"r\\s', "plain"]:
            with tempfile.TemporaryDirectory() as d:
                p = os.path.join(d, ".env")
                Path(p).write_text("K=" + sl.format_env_value(secret) + "\n")
                self.assertEqual(dotenv_values(p, interpolate=False)["K"], secret)


class RemoteEnvMerge(unittest.TestCase):
    def run_merge(self, path, stdin):
        return subprocess.run([sys.executable, "-c", sl.REMOTE_ENV_MERGE, path],
                              input=stdin, text=True, check=True)

    def test_replace_append_preserve(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, ".env")
            Path(p).write_text("# comment\nFOO=1\nSOLAREDGE_CLIENT_ID=old\nBAR=2")
            self.run_merge(p, "SOLAREDGE_CLIENT_ID=new\nSOLAREDGE_CLIENT_SECRET=sec\n")
            self.assertEqual(
                Path(p).read_text(),
                "# comment\nFOO=1\nSOLAREDGE_CLIENT_ID=new\nBAR=2\n"
                "SOLAREDGE_CLIENT_SECRET=sec\n")
            self.assertEqual(stat.S_IMODE(os.stat(p).st_mode), 0o600)

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, ".env")
            Path(p).write_text("A=1\n")
            inp = "SOLAREDGE_CLIENT_ID=i\nSOLAREDGE_CLIENT_SECRET=s\n"
            self.run_merge(p, inp)
            first = Path(p).read_text()
            self.run_merge(p, inp)
            self.assertEqual(first, Path(p).read_text())

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, ".env")
            self.run_merge(p, "SOLAREDGE_CLIENT_ID=i\n")
            self.assertEqual(Path(p).read_text(), "SOLAREDGE_CLIENT_ID=i\n")
            self.assertEqual(stat.S_IMODE(os.stat(p).st_mode), 0o600)

    def test_duplicates_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, ".env")
            Path(p).write_text("K=1\nexport K=2\nZ=3\n")
            self.run_merge(p, "K=9\n")
            self.assertEqual(Path(p).read_text(), "K=9\nZ=3\n")


class CallbackServerTest(unittest.TestCase):
    def _serve(self, path):
        server = sl.CallbackServer(0)
        self.addCleanup(server.server_close)
        t = threading.Thread(target=server.handle_request)
        t.start()
        port = server.server_address[1]
        try:
            return server, urllib.request.urlopen(
                "http://127.0.0.1:%d%s" % (port, path), timeout=5)
        except urllib.error.HTTPError as e:
            return server, e
        finally:
            t.join(5)

    def test_callback_captured(self):
        server, resp = self._serve("/callback?code=c&site_id=42")
        self.assertEqual(resp.status, 200)
        self.assertIn("erfolgreich", resp.read().decode("utf-8"))
        self.assertEqual(server.result, {"code": ["c"], "site_id": ["42"]})

    def test_other_path_404(self):
        server, resp = self._serve("/favicon.ico")
        self.assertEqual(resp.code, 404)
        self.assertIsNone(server.result)

    def test_binds_loopback(self):
        server = sl.CallbackServer(0)
        self.addCleanup(server.server_close)
        self.assertEqual(server.server_address[0], "127.0.0.1")


def _ok(returncode=0, stdout=""):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


class UploadAndFlow(unittest.TestCase):
    payload = {"version": 1, "access_token": "ACCESSTOK", "refresh_token": "REFRESHTOK",
               "token_type": "Bearer", "expires_at": 2.0, "obtained_at": 1.0,
               "granted_at": 1.0, "site_id": "42"}

    def test_upload_sequence_and_cleanup(self):
        seen_dirs = []
        calls = []

        def fake_run(args, **kw):
            calls.append(args)
            if args[0] == "scp":
                local = args[2]
                seen_dirs.append(os.path.dirname(local))
                self.assertEqual(stat.S_IMODE(os.stat(local).st_mode), 0o600)
                self.assertEqual(json.load(open(local))["site_id"], "42")
            if "stat" in args[-1]:
                return _ok(stdout="600\n")
            return _ok()

        with mock.patch.object(sl.subprocess, "run", side_effect=fake_run):
            sl.upload_token_file(self.payload, "h", "/home/pi/app")
        self.assertEqual(calls[0][0], "scp")
        self.assertTrue(calls[0][3].endswith(":/home/pi/app/.tokens.json.upload"))
        self.assertIn("mv -f", calls[1][-1])
        self.assertIn("chmod 600", calls[1][-1])
        self.assertFalse(os.path.exists(seen_dirs[0]))
        for c in calls:  # no secrets in argv
            for a in c:
                self.assertNotIn("ACCESSTOK", a)
                self.assertNotIn("REFRESHTOK", a)

    def test_upload_failure_still_cleans_up(self):
        dirs = []

        def fake_run(args, **kw):
            if args[0] == "scp":
                dirs.append(os.path.dirname(args[2]))
                return _ok()
            return _ok(returncode=1)

        with mock.patch.object(sl.subprocess, "run", side_effect=fake_run):
            with self.assertRaises(sl.LoginError):
                sl.upload_token_file(self.payload, "h", "/d")
        self.assertFalse(os.path.exists(dirs[0]))

    def test_upload_wrong_mode_fails(self):
        def fake_run(args, **kw):
            if "stat" in args[-1]:
                return _ok(stdout="644\n")
            return _ok()

        with mock.patch.object(sl.subprocess, "run", side_effect=fake_run):
            with self.assertRaises(sl.LoginError):
                sl.upload_token_file(self.payload, "h", "/d")

    def test_env_update_secret_via_stdin_only(self):
        with mock.patch.object(sl.subprocess, "run", return_value=_ok()) as run:
            sl.update_remote_env("h", "/d", "CID", "SUPERSECRET")
        args = run.call_args[0][0]
        for a in args:
            self.assertNotIn("SUPERSECRET", a)
        self.assertIn("SOLAREDGE_CLIENT_SECRET=SUPERSECRET", run.call_args[1]["input"])

    def test_exchange_code_request(self):
        resp = mock.MagicMock()
        resp.__enter__.return_value.read.return_value = b'{"access_token": "a"}'
        with mock.patch.object(sl.urllib.request, "urlopen", return_value=resp) as uo:
            out = sl.exchange_code("CODE", "cid", "sec")
        self.assertEqual(out, {"access_token": "a"})
        req = uo.call_args[0][0]
        self.assertEqual(req.get_header("Content-type"), "application/json")
        body = json.loads(req.data.decode())
        self.assertEqual(body["grant_type"], "authorization_code")
        self.assertEqual(body["redirect_uri"], sl.REDIRECT_URI)

    def test_exchange_http_error_hides_secret(self):
        err = urllib.error.HTTPError(
            sl.TOKEN_URL, 400, "Bad", {}, io.BytesIO(b'{"error": "invalid_grant"}'))
        with mock.patch.object(sl.urllib.request, "urlopen", side_effect=err):
            with self.assertRaises(sl.LoginError) as cm:
                sl.exchange_code("CODE", "cid", "SUPERSECRET")
        self.assertIn("400", str(cm.exception))
        self.assertNotIn("SUPERSECRET", str(cm.exception))

    def test_secrets_only_flow(self):
        with mock.patch.object(sl, "read_op_credentials", return_value=("i", "s")), \
                mock.patch.object(sl, "update_remote_env") as upd, \
                mock.patch.object(sl.webbrowser, "open") as wb, \
                mock.patch.object(sl, "CallbackServer") as srv:
            rc = sl.main(["--secrets-only"])
        self.assertEqual(rc, 0)
        upd.assert_called_once()
        wb.assert_not_called()
        srv.assert_not_called()

    def test_op_uses_personal_account(self):
        item = {"fields": [{"label": "Client ID", "value": "cid"},
                           {"label": "Client Secret", "value": "sec"},
                           {"label": "username", "value": "u"},
                           {"label": "password", "value": "p"}]}
        done = mock.Mock(returncode=0, stdout=json.dumps(item), stderr="")
        with mock.patch.object(sl.shutil, "which", return_value="/usr/bin/op"), \
                mock.patch.object(sl.subprocess, "run", return_value=done) as run:
            self.assertEqual(sl.read_op_credentials(sl.OP_ITEM, None, None), ("cid", "sec"))
        cmd = run.call_args[0][0]
        self.assertEqual(cmd[cmd.index("--account") + 1], "my.1password.com")

    def test_main_login_error_exit_1(self):
        with mock.patch.object(sl, "read_op_credentials",
                               side_effect=sl.LoginError("boom")):
            self.assertEqual(sl.main([]), 1)


if __name__ == "__main__":
    unittest.main()
