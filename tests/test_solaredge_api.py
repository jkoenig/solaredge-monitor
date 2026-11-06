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


NOW_FIXED = datetime(2026, 11, 5, 14, 0, 0, tzinfo=SITE_TZ)


def ts(i, v):
    return {"timestamp": f"2026-11-05T13:{i:02d}:00+01:00", "value": v}


def telemetry_body(soc, charge, discharge, remaining, serial=FAKE_SERIAL):
    return {
        "period": {},
        "resolution": "QUARTER_HOUR",
        "storage": {
            serial: {
                "chargePower": {"unit": "W", "values": [ts(0, 1.0), ts(15, charge), ts(30, None)]},
                "dischargePower": {"unit": "W", "values": [ts(0, 1.0), ts(15, discharge), ts(30, None)]},
                # Live API sends PERCENTAGE as a 0..1 fraction; callers pass percent.
                "stateOfEnergy": {"unit": "PERCENTAGE", "values": [ts(0, 0.64), ts(15, soc / 100.0), ts(30, None)]},
                "remainingEnergy": {"unit": "WH", "values": [ts(0, 1.0), ts(15, remaining), ts(30, None)]},
                "acGridChargingEnergy": {"unit": "WH", "values": []},
            }
        },
    }


class BatteryTelemetryTests(unittest.TestCase):
    def test_charging(self):
        api, store, _ = make_api([fake_response(200, telemetry_body(65.0, 1500.0, 0.0, 6200.0))], now=NOW_FIXED)
        b = api.get_battery_telemetry(internal_temp=21.0)
        self.assertIsInstance(b, BatteryData)
        self.assertEqual(b.state_of_charge, 65)
        self.assertIsInstance(b.state_of_charge, int)
        self.assertEqual(b.status, "Charge")
        self.assertAlmostEqual(b.power, 1.5)
        self.assertAlmostEqual(b.available_energy, 6.2)
        self.assertEqual(b.internal_temp, 21.0)

    def test_discharging(self):
        api, _, _ = make_api([fake_response(200, telemetry_body(50.0, 0.0, 800.0, 3000.0))], now=NOW_FIXED)
        b = api.get_battery_telemetry()
        self.assertEqual(b.status, "Discharge")
        self.assertAlmostEqual(b.power, -0.8)

    def test_idle_thresholds(self):
        for charge, discharge, expected in [(30, 0, "Idle"), (0, 49, "Idle"), (50, 0, "Idle"), (51, 0, "Charge")]:
            with self.subTest(charge=charge, discharge=discharge):
                api, _, _ = make_api([fake_response(200, telemetry_body(50.0, charge, discharge, 1000.0))], now=NOW_FIXED)
                self.assertEqual(api.get_battery_telemetry().status, expected)

    def test_soc_rounding(self):
        api, _, _ = make_api([fake_response(200, telemetry_body(64.6, 0.0, 0.0, 1000.0))], now=NOW_FIXED)
        self.assertEqual(api.get_battery_telemetry().state_of_charge, 65)

    def test_soc_fraction_scaled_to_percent(self):
        api, _, _ = make_api([fake_response(200, telemetry_body(11.11111, 0.0, 0.0, 983.0))], now=NOW_FIXED)
        self.assertEqual(api.get_battery_telemetry().state_of_charge, 11)

    def test_soc_full_is_100(self):
        api, _, _ = make_api([fake_response(200, telemetry_body(100.0, 0.0, 0.0, 9200.0))], now=NOW_FIXED)
        self.assertEqual(api.get_battery_telemetry().state_of_charge, 100)

    def test_null_and_missing_metrics_are_zero(self):
        body = {"storage": {FAKE_SERIAL: {
            "stateOfEnergy": {"unit": "PERCENTAGE", "values": [ts(0, None)]},
            "chargePower": {"unit": "W", "values": []},
        }}}
        api, _, _ = make_api([fake_response(200, body)], now=NOW_FIXED)
        b = api.get_battery_telemetry()
        self.assertEqual(b.state_of_charge, 0)
        self.assertEqual(b.power, 0.0)
        self.assertEqual(b.available_energy, 0.0)
        self.assertEqual(b.status, "Idle")

    def test_empty_storage_is_none(self):
        api, _, _ = make_api([fake_response(200, {"storage": {}})], now=NOW_FIXED)
        self.assertIsNone(api.get_battery_telemetry())

    def test_two_batteries_aggregate(self):
        a = telemetry_body(60.0, 1000.0, 0.0, 2000.0, serial="SN-A")
        b = telemetry_body(70.0, 500.0, 0.0, 3000.0, serial="SN-B")
        a["storage"].update(b["storage"])
        api, _, _ = make_api([fake_response(200, a)], now=NOW_FIXED)
        r = api.get_battery_telemetry()
        self.assertAlmostEqual(r.power, 1.5)
        self.assertAlmostEqual(r.available_energy, 5.0)
        self.assertEqual(r.state_of_charge, 65)

    def test_request_window_has_offset(self):
        api, store, _ = make_api([fake_response(200, telemetry_body(65.0, 0.0, 0.0, 1.0))], now=NOW_FIXED)
        api.get_battery_telemetry()
        args, kwargs = store.authorized_request.call_args
        self.assertTrue(args[1].endswith("/sites/%s/storage/telemetry" % FAKE_SITE_ID))
        params = kwargs["params"]
        self.assertEqual(params["resolution"], "QUARTER_HOUR")
        start = datetime.fromisoformat(params["from"])
        end = datetime.fromisoformat(params["to"])
        self.assertIsNotNone(start.tzinfo)
        self.assertIsNotNone(end.tzinfo)
        self.assertEqual((end - start).total_seconds(), 3600)

    def test_503_single_attempt(self):
        api, store, sleep = make_api([fake_response(503), fake_response(200, {})], now=NOW_FIXED)
        self.assertIsNone(api.get_battery_telemetry())
        self.assertEqual(store.authorized_request.call_count, 1)
        sleep.assert_not_called()


def status_body(values):
    return {"storage": {FAKE_SERIAL: {
        "batteryState": {"unit": "CODE", "values": [ts(0, 3)]},
        "internalTemperature": {"unit": "CELSIUS", "values": values},
    }}}


class StorageTemperatureTests(unittest.TestCase):
    def test_last_non_null(self):
        api, _, _ = make_api([fake_response(200, status_body([ts(0, 20.5), ts(15, None)]))], now=NOW_FIXED)
        self.assertEqual(api.get_storage_temperature(), 20.5)

    def test_all_null_is_zero(self):
        api, _, _ = make_api([fake_response(200, status_body([ts(0, None)]))], now=NOW_FIXED)
        self.assertEqual(api.get_storage_temperature(), 0.0)

    def test_failed_and_empty(self):
        api, _, _ = make_api([fake_response(500)], now=NOW_FIXED)
        self.assertIsNone(api.get_storage_temperature())
        api, _, _ = make_api([fake_response(200, {"storage": {}})], now=NOW_FIXED)
        self.assertIsNone(api.get_storage_temperature())

    def test_window_two_hours_with_offset(self):
        api, store, _ = make_api([fake_response(200, status_body([ts(0, 1.0)]))], now=NOW_FIXED)
        api.get_storage_temperature()
        args, kwargs = store.authorized_request.call_args
        self.assertTrue(args[1].endswith("/storage/status"))
        params = kwargs["params"]
        self.assertEqual(params["resolution"], "QUARTER_HOUR")
        start = datetime.fromisoformat(params["from"])
        end = datetime.fromisoformat(params["to"])
        self.assertIsNotNone(start.tzinfo)
        self.assertEqual((end - start).total_seconds(), 7200)

    def test_503_single_attempt(self):
        api, store, sleep = make_api([fake_response(503), fake_response(200, {})], now=NOW_FIXED)
        self.assertIsNone(api.get_storage_temperature())
        self.assertEqual(store.authorized_request.call_count, 1)
        sleep.assert_not_called()


NOW_HISTORY = datetime(2026, 11, 5, 9, 0, 0, tzinfo=SITE_TZ)
HIST_DATES = [f"2026-10-{d}" for d in range(23, 32)] + [f"2026-11-0{d}" for d in range(1, 6)]


def day_ts(date_str):
    offset = "+02:00" if date_str <= "2026-10-24" else "+01:00"
    return f"{date_str}T00:00:00{offset}"


def energy_body(values_wh):
    return {
        "period": {},
        "unit": "WH",
        "resolution": "DAY",
        "values": [{"timestamp": day_ts(d), "value": v} for d, v in zip(HIST_DATES, values_wh)],
    }


def meters_body(values_wh, extra=None):
    meters = {
        "CONSUMPTION": {
            "consumptionEnergy": {
                "unit": "WH",
                "values": [{"timestamp": day_ts(d), "value": v} for d, v in zip(HIST_DATES, values_wh)],
            }
        }
    }
    if extra:
        meters.update(extra)
    return {"period": {}, "resolution": "DAY", "meters": meters}


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.prod = [1000.0 * (i + 1) for i in range(14)]
        self.cons = [500.0 * (i + 1) for i in range(14)]

    def test_dates_and_production(self):
        api, _, _ = make_api(
            [fake_response(200, energy_body(self.prod)), fake_response(200, meters_body(self.cons))],
            now=NOW_HISTORY,
        )
        h = api.get_energy_history()
        self.assertIsInstance(h, EnergyHistory)
        self.assertEqual(h.dates, HIST_DATES)
        self.assertEqual(len(h.dates), 14)
        self.assertEqual(h.production, [v / 1000.0 for v in self.prod])
        self.assertEqual(h.consumption, [v / 1000.0 for v in self.cons])

    def test_two_requests_and_windows(self):
        api, store, _ = make_api(
            [fake_response(200, energy_body(self.prod)), fake_response(200, meters_body(self.cons))],
            now=NOW_HISTORY,
        )
        api.get_energy_history()
        self.assertEqual(store.authorized_request.call_count, 2)
        first, second = store.authorized_request.call_args_list
        self.assertTrue(first.args[1].endswith("/energy"))
        self.assertTrue(second.args[1].endswith("/meters/telemetry"))
        self.assertEqual(first.kwargs["params"]["resolution"], "DAY")
        self.assertEqual(first.kwargs["params"]["unit"], "WH")
        self.assertEqual(second.kwargs["params"]["resolution"], "DAY")
        for call in (first, second):
            p = call.kwargs["params"]
            self.assertTrue(p["from"].startswith("2026-10-23T00:00:00+02:00"))
            self.assertIsNotNone(datetime.fromisoformat(p["from"]).tzinfo)
            self.assertIsNotNone(datetime.fromisoformat(p["to"]).tzinfo)

    def test_null_bucket_and_multi_meter(self):
        cons = list(self.cons)
        cons[3] = None
        extra = {
            "SN-METER-2": {"consumptionEnergy": {"unit": "WH", "values": [
                {"timestamp": day_ts(HIST_DATES[0]), "value": 250.0}]}},
            "PRODUCTION-ONLY": {"productionEnergy": {"unit": "WH", "values": [
                {"timestamp": day_ts(HIST_DATES[0]), "value": 99999.0}]}},
        }
        api, _, _ = make_api(
            [fake_response(200, energy_body(self.prod)), fake_response(200, meters_body(cons, extra))],
            now=NOW_HISTORY,
        )
        h = api.get_energy_history()
        self.assertEqual(h.consumption[3], 0.0)
        self.assertAlmostEqual(h.consumption[0], 0.5 + 0.25)
        self.assertAlmostEqual(h.consumption[1], 1.0)

    def test_missing_date_is_zero(self):
        body = energy_body(self.prod)
        body["values"].pop(5)
        api, _, _ = make_api(
            [fake_response(200, body), fake_response(200, meters_body(self.cons))], now=NOW_HISTORY
        )
        h = api.get_energy_history()
        self.assertEqual(h.production[5], 0.0)
        self.assertEqual(h.production[6], 7.0)

    def test_energy_failure_skips_meters(self):
        api, store, sleep = make_api(
            [fake_response(503), fake_response(200, meters_body(self.cons))], now=NOW_HISTORY
        )
        self.assertIsNone(api.get_energy_history())
        self.assertEqual(store.authorized_request.call_count, 1)
        sleep.assert_not_called()

    def test_meters_failure_is_none(self):
        api, store, _ = make_api(
            [fake_response(200, energy_body(self.prod)), fake_response(503)], now=NOW_HISTORY
        )
        self.assertIsNone(api.get_energy_history())
        self.assertEqual(store.authorized_request.call_count, 2)

    def test_malformed_is_none(self):
        api, _, _ = make_api(
            [fake_response(200, {"unit": "WH"}), fake_response(200, meters_body(self.cons))], now=NOW_HISTORY
        )
        self.assertIsNone(api.get_energy_history())


class ModelsCleanupTests(unittest.TestCase):
    def test_v1_models_removed(self):
        self.assertFalse(hasattr(models, "PowerFlow"))
        self.assertFalse(hasattr(models, "SiteOverview"))
        self.assertTrue(hasattr(solaredge_api, "SolarEdgeAPI"))


if __name__ == "__main__":
    unittest.main()
