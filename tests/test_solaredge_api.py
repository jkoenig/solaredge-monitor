"""Tests for the V2 SolarEdge client (stdlib unittest, mocked transport, fake data only)."""

import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

import models  # noqa: E402
import solaredge_api  # noqa: E402
from models import BatteryData, EnergyDetails, EnergyHistory  # noqa: E402
from solaredge_api import (  # noqa: E402
    BASE_URL,
    SITE_TZ,
    SolarEdgeAPI,
    derive_battery_status,
    last_non_null,
    to_kwh,
)
from token_store import LoginRequired, TransientAuthError  # noqa: E402

FAKE_SITE_ID = "98765432"
FAKE_SERIAL = "SN-TEST-ACTIVE"


def fake_response(status=200, body=None, json_error=False, headers=None):
    resp = mock.MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    if json_error:
        resp.json.side_effect = ValueError("no json")
    else:
        resp.json.return_value = body if body is not None else {}
    return resp


def make_api(side_effect, now=None):
    store = mock.MagicMock()
    store.site_id = FAKE_SITE_ID
    store.authorized_request.side_effect = side_effect
    sleep = mock.MagicMock()
    kwargs = {}
    if now is not None:
        kwargs["now_fn"] = lambda: now
    api = SolarEdgeAPI(store, sleep=sleep, **kwargs)
    return api, store, sleep


OVERVIEW_BODY = {
    "siteId": 1,
    "production": {
        "total": 12345.0,
        "unit": "WH",
        "toSelfConsumption": 4000.0,
        "toStorage": None,
        "toGrid": 3000.0,
    },
    "consumption": {
        "total": 9000.0,
        "unit": "WH",
        "fromPv": 5000.0,
        "fromStorage": 2000.0,
        "fromGrid": None,
    },
}


class HelperTests(unittest.TestCase):
    def test_to_kwh_units(self):
        self.assertEqual(to_kwh(None, "WH"), 0.0)
        self.assertAlmostEqual(to_kwh(1500, "WH"), 1.5)
        self.assertAlmostEqual(to_kwh(2.5, "KWH"), 2.5)
        self.assertAlmostEqual(to_kwh(2, "MWH"), 2000.0)
        self.assertAlmostEqual(to_kwh(1, "GWH"), 1_000_000.0)
        with self.assertRaises(ValueError):
            to_kwh(1, "FOO")

    def test_last_non_null(self):
        vals = [{"timestamp": "a", "value": 1.0}, {"timestamp": "b", "value": 2.0}, {"timestamp": "c", "value": None}]
        self.assertEqual(last_non_null(vals), 2.0)
        self.assertIsNone(last_non_null([{"timestamp": "a", "value": None}]))
        self.assertIsNone(last_non_null([]))

    def test_derive_status_boundaries(self):
        self.assertEqual(derive_battery_status(30), "Idle")
        self.assertEqual(derive_battery_status(-49), "Idle")
        self.assertEqual(derive_battery_status(50), "Idle")
        self.assertEqual(derive_battery_status(-50), "Idle")
        self.assertEqual(derive_battery_status(51), "Charge")
        self.assertEqual(derive_battery_status(-51), "Discharge")


class OverviewTests(unittest.TestCase):
    def test_parse_wh_with_nulls(self):
        api, store, _ = make_api([fake_response(200, OVERVIEW_BODY)])
        result = api.get_overview()
        self.assertEqual(result.production, 12.345)
        self.assertEqual(result.self_consumption, 4.0)
        self.assertEqual(result.to_storage, 0.0)
        self.assertEqual(result.feed_in, 3.0)
        self.assertEqual(result.consumption, 9.0)
        self.assertEqual(result.from_pv, 5.0)
        self.assertEqual(result.from_storage, 2.0)
        self.assertEqual(result.purchased, 0.0)
        self.assertIsInstance(result, EnergyDetails)

    def test_request_url_and_method(self):
        api, store, _ = make_api([fake_response(200, OVERVIEW_BODY)])
        api.get_overview()
        args, kwargs = store.authorized_request.call_args
        self.assertEqual(args, ("GET", f"{BASE_URL}/sites/{FAKE_SITE_ID}/overview"))
        self.assertIsNone(kwargs.get("params"))

    def test_kwh_unit_as_is(self):
        body = {
            "production": {"total": 12.5, "unit": "KWH"},
            "consumption": {"total": 7.0, "unit": "KWH", "fromGrid": 1.0},
        }
        api, _, _ = make_api([fake_response(200, body)])
        r = api.get_overview()
        self.assertEqual(r.production, 12.5)
        self.assertEqual(r.consumption, 7.0)
        self.assertEqual(r.purchased, 1.0)

    def test_missing_consumption_is_zero(self):
        body = {"production": {"total": 1000.0, "unit": "WH"}}
        api, _, _ = make_api([fake_response(200, body)])
        r = api.get_overview()
        self.assertEqual(r.production, 1.0)
        self.assertEqual(r.consumption, 0.0)
        self.assertEqual(r.from_pv, 0.0)
        self.assertEqual(r.from_storage, 0.0)
        self.assertEqual(r.purchased, 0.0)

    def test_unknown_unit_returns_none_and_logs_error(self):
        body = {"production": {"total": 1.0, "unit": "FOO"}}
        api, _, _ = make_api([fake_response(200, body)])
        with self.assertLogs(level="ERROR"):
            self.assertIsNone(api.get_overview())

    def test_retry_503_then_200(self):
        api, store, sleep = make_api([fake_response(503), fake_response(200, OVERVIEW_BODY)])
        self.assertIsNotNone(api.get_overview())
        self.assertEqual(store.authorized_request.call_count, 2)
        sleep.assert_called_once()

    def test_503_twice(self):
        api, store, sleep = make_api([fake_response(503), fake_response(503)])
        self.assertIsNone(api.get_overview())
        self.assertEqual(store.authorized_request.call_count, 2)

    def test_timeout_then_200(self):
        api, store, sleep = make_api([requests.exceptions.Timeout(), fake_response(200, OVERVIEW_BODY)])
        self.assertIsNotNone(api.get_overview())
        self.assertEqual(store.authorized_request.call_count, 2)
        sleep.assert_called_once()

    def test_timeout_twice(self):
        api, store, _ = make_api([requests.exceptions.Timeout(), requests.exceptions.Timeout()])
        self.assertIsNone(api.get_overview())
        self.assertEqual(store.authorized_request.call_count, 2)

    def test_no_retry_flag_503(self):
        api, store, sleep = make_api([fake_response(503), fake_response(200, OVERVIEW_BODY)])
        self.assertIsNone(api.get_overview(retry=False))
        self.assertEqual(store.authorized_request.call_count, 1)
        sleep.assert_not_called()

    def test_no_retry_flag_timeout(self):
        api, store, sleep = make_api([requests.exceptions.Timeout(), fake_response(200, OVERVIEW_BODY)])
        self.assertIsNone(api.get_overview(retry=False))
        self.assertEqual(store.authorized_request.call_count, 1)
        sleep.assert_not_called()

    def test_non_retryable_statuses(self):
        for status in (400, 403, 404, 429):
            with self.subTest(status=status):
                api, store, sleep = make_api([fake_response(status), fake_response(200, OVERVIEW_BODY)])
                self.assertIsNone(api.get_overview())
                self.assertEqual(store.authorized_request.call_count, 1)
                sleep.assert_not_called()

    def test_429_logs_ratelimit_header(self):
        api, _, _ = make_api([fake_response(429, headers={"x-ratelimit-remaining-minute": "7"})])
        with self.assertLogs(level="ERROR") as cm:
            api.get_overview()
        self.assertIn("7", "\n".join(cm.output))
        self.assertIn("x-ratelimit-remaining-minute", "\n".join(cm.output))

    def test_connection_error(self):
        api, store, _ = make_api([requests.exceptions.ConnectionError("boom")])
        self.assertIsNone(api.get_overview())
        self.assertEqual(store.authorized_request.call_count, 1)

    def test_transient_auth_error(self):
        api, _, _ = make_api([TransientAuthError("deferred")])
        self.assertIsNone(api.get_overview())

    def test_login_required_propagates(self):
        api, _, _ = make_api([LoginRequired("expired")])
        with self.assertRaises(LoginRequired):
            api.get_overview()

    def test_login_required_from_site_id_propagates(self):
        api, store, _ = make_api([fake_response(200, OVERVIEW_BODY)])
        type(store).site_id = mock.PropertyMock(side_effect=LoginRequired("missing"))
        with self.assertRaises(LoginRequired):
            api.get_overview()

    def test_malformed_bodies(self):
        api, _, _ = make_api([fake_response(200, json_error=True)])
        self.assertIsNone(api.get_overview())
        api, _, _ = make_api([fake_response(200, [1, 2])])
        self.assertIsNone(api.get_overview())


class DetectBatteryTests(unittest.TestCase):
    def test_active_true(self):
        body = [{"active": False, "serialNumber": "SN-X"}, {"active": True, "serialNumber": FAKE_SERIAL}]
        api, store, _ = make_api([fake_response(200, body)])
        self.assertIs(api.detect_battery(), True)
        self.assertEqual(store.authorized_request.call_args.kwargs["params"], {"types": "BATTERY"})

    def test_only_inactive(self):
        api, _, _ = make_api([fake_response(200, [{"active": False}])])
        self.assertIs(api.detect_battery(), False)

    def test_empty(self):
        api, _, _ = make_api([fake_response(200, [])])
        self.assertIs(api.detect_battery(), False)

    def test_non_list_and_failed(self):
        api, _, _ = make_api([fake_response(200, {"a": 1})])
        self.assertIsNone(api.detect_battery())
        api, _, _ = make_api([fake_response(404)])
        self.assertIsNone(api.detect_battery())

    def test_503_single_attempt(self):
        api, store, sleep = make_api([fake_response(503), fake_response(200, [])])
        self.assertIsNone(api.detect_battery())
        self.assertEqual(store.authorized_request.call_count, 1)
        sleep.assert_not_called()


class LogHygieneTests(unittest.TestCase):
    def test_no_site_id_or_serial_in_logs(self):
        body = [{"active": True, "serialNumber": FAKE_SERIAL}]
        api, _, _ = make_api([fake_response(503), fake_response(200, OVERVIEW_BODY), fake_response(200, body)])
        with self.assertLogs(level="DEBUG") as cm:
            api.get_overview(retry=False)
            api.get_overview()
            api.detect_battery()
        joined = "\n".join(cm.output)
        self.assertNotIn(FAKE_SITE_ID, joined)
        self.assertNotIn(FAKE_SERIAL, joined)
        self.assertIn("{site_id}", joined)


if __name__ == "__main__":
    unittest.main()
