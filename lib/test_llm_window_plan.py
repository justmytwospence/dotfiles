"""Tests for llm-window-plan's usage model and window policy; no network or live state."""
import importlib.machinery
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "dot_local/bin/executable_llm-window-plan"
loader = importlib.machinery.SourceFileLoader("llm_window_plan", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
p = importlib.util.module_from_spec(spec)
loader.exec_module(p)

UTC = timezone.utc
DAY0 = datetime(2026, 9, 1, tzinfo=UTC).timestamp()
BIN = p.BIN


def heavy_day(t, rate=5.0):
    """5% of the 5-hour budget per 10 minutes from 09:00 to 19:00 UTC."""
    h = datetime.fromtimestamp(t, UTC).hour
    return rate if 9 <= h < 19 else 0.0


def account(days, demand=heavy_day):
    """Samples the usage API would report every 10 minutes, windows started by use."""
    out, start, used = [], None, 0.0
    for i in range(days * p.BINS_PER_DAY):
        t = DAY0 + i * BIN
        if start is not None and t >= start + p.WINDOW:
            start, used = None, 0.0
        d = demand(t)
        if start is None and d > 0:
            start = t
        if start is not None:
            used = min(100.0, used + d)
        reset = start + p.WINDOW if start is not None else None
        out.append({"t": t + BIN, "u5": used, "reset5": reset, "capped": used >= 100 and reset is not None})
    return out


class Policy(unittest.TestCase):
    def test_heavy_day_anchors_early_morning_for_three_windows(self):
        demand = [heavy_day(DAY0 + i * BIN) for i in range(p.HORIZON)]
        organic = p.simulate(demand, None)
        self.assertEqual(len(organic[2]), 2)
        self.assertAlmostEqual(organic[0], 100)
        best, _ = p.plan(type("P", (), {"demand": lambda self, t: heavy_day(t)})(), DAY0)
        self.assertIsNotNone(best[0])
        self.assertTrue(6 * 6 <= best[0] <= 7 * 6 + 2, best[0])
        self.assertEqual(len(best[3]), 3)
        self.assertAlmostEqual(best[2], 50)

    def test_decide_learns_anchor_from_samples(self):
        samples = account(10)
        now = DAY0 + 10 * 86400
        d = p.decide(samples, now, UTC)
        self.assertEqual(d["action"], "wait", d)
        hour = (d["at"] - now) / 3600
        self.assertTrue(6 <= hour <= 7 + 1 / 3, d)

    def test_light_use_never_pings(self):
        samples = account(10, lambda t: heavy_day(t, rate=0.5))
        d = p.decide(samples, DAY0 + 10 * 86400, UTC)
        self.assertEqual((d["action"], d["at"]), ("wait", None), d)

    def test_learning_period_keeps_pinging_at_expiry(self):
        samples = account(3)
        d = p.decide(samples, DAY0 + 3 * 86400, UTC)
        self.assertEqual(d["action"], "ping")
        self.assertIn("learning", d["reason"])

    def test_running_window_waits_for_reset(self):
        now = DAY0 + 3600
        samples = [{"t": now - 60, "u5": 40.0, "reset5": now + 1800, "capped": False}]
        d = p.decide(samples, now, UTC)
        self.assertEqual((d["action"], d["reset"], d["at"]), ("wait", now + 1800, now + 1800 + p.BUFFER))


class Profile(unittest.TestCase):
    def test_new_window_counts_its_usage(self):
        a = {"t": 0, "u5": 80.0, "reset5": 100, "capped": False}
        b = {"t": BIN, "u5": 7.0, "reset5": BIN + p.WINDOW, "capped": False}
        self.assertEqual([d for _, d, _ in p.intervals([a, b])], [7.0])

    def test_same_window_counts_delta_despite_reset_jitter(self):
        a = {"t": 0, "u5": 10.0, "reset5": 9000.4, "capped": False}
        b = {"t": BIN, "u5": 14.0, "reset5": 9001.0, "capped": False}
        self.assertEqual([d for _, d, _ in p.intervals([a, b])], [4.0])

    def test_gap_is_unobserved(self):
        a = {"t": 0, "u5": 10.0, "reset5": 99999, "capped": False}
        b = {"t": 4 * BIN, "u5": 50.0, "reset5": 99999, "capped": False}
        self.assertEqual(list(p.intervals([a, b])), [])

    def test_capped_time_keeps_demand(self):
        samples = account(10)
        prof = p.Profile(samples, DAY0 + 10 * 86400, UTC)
        self.assertGreater(prof.capped_bins, 0)
        # 13:00 is blocked every day (the 09:00 window ran out), yet demand stays ~5%.
        self.assertAlmostEqual(prof.demand(DAY0 + 13 * 3600), 5.0, delta=0.5)


class Sampling(unittest.TestCase):
    def test_parse_usage(self):
        s = p.parse_usage({"five_hour": {"utilization": 100, "resets_at": "2026-10-19T12:10:00.36+00:00"},
                           "seven_day": {"utilization": 65, "resets_at": None}},
                          datetime(2026, 10, 19, 11, tzinfo=UTC).timestamp())
        self.assertEqual((s["u5"], s["u7"], s["capped"]), (100.0, 65, True))
        self.assertIsNone(p.parse_usage({"five_hour": None}, 0))

    def test_expired_token_skips_without_request(self):
        with tempfile.TemporaryDirectory() as d:
            creds = os.path.join(d, "c.json")
            Path(creds).write_text(json.dumps({"claudeAiOauth": {"accessToken": "x", "expiresAt": 1000}}))
            s, why = p.fetch(10_000, creds)
            self.assertIsNone(s)
            self.assertIn("expired", why)

    def test_store_prunes_and_dedupes(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "u.jsonl")
            now = 100 * 86400
            self.assertTrue(p.store({"t": now - p.KEEP - 1, "u5": 1.0}, now, path))
            self.assertTrue(p.store({"t": now, "u5": 2.0}, now, path))
            self.assertFalse(p.store({"t": now + 30, "u5": 2.0}, now, path))
            self.assertEqual([s["t"] for s in p.load_samples(path)], [now])


if __name__ == "__main__":
    unittest.main()
