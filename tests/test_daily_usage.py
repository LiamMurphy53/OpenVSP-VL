import unittest
from datetime import datetime, timezone
from tools.check_daily_usage import evaluate


class DailyUsageGuard(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 13, 23, 50, tzinfo=timezone.utc)
        self.sample = {'usedPercent': 5, 'resetsAt': 1792509446}
        self.state, _ = evaluate(None, self.sample, self.now, initialize=True)

    def check(self, percent, now=None, reset=None):
        sample = dict(self.sample, usedPercent=percent)
        if reset is not None:
            sample['resetsAt'] = reset
        self.state, result = evaluate(self.state, sample, now or self.now)
        return result

    def test_threshold_and_repeated_checks(self):
        self.assertEqual(self.check(14)['decision'], 'CONTINUE')
        self.assertEqual(self.check(14)['spentPoints'], 9)
        self.assertEqual(self.check(15)['decision'], 'STOP')
        self.assertEqual(self.check(15)['decision'], 'STOP')

    def test_reset_cannot_grant_more_same_day(self):
        self.check(10)
        self.assertEqual(self.check(0, reset=1792609446)['decision'], 'STOP')
        self.assertEqual(self.check(1, reset=1792609446)['decision'], 'STOP')

    def test_meter_decrease_stops(self):
        self.assertEqual(self.check(4)['decision'], 'STOP')

    def test_denver_midnight_new_day_no_carry(self):
        self.check(15)
        before = datetime(2026, 10, 14, 5, 59, tzinfo=timezone.utc)
        self.assertEqual(self.check(12, before)['decision'], 'STOP')
        after = datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc)
        result = self.check(12, after)
        self.assertEqual(result['day'], '2026-10-14')
        self.assertEqual(result['spentPoints'], 0)
        self.assertEqual(result['decision'], 'CONTINUE')

    def test_missing_ledger_fails_closed(self):
        with self.assertRaises(ValueError):
            evaluate(None, self.sample, self.now)

    def test_invalid_meter_fails_closed(self):
        for value in [None, True, -1, 101, float('nan')]:
            with self.assertRaises((ValueError, TypeError)):
                evaluate(self.state, dict(self.sample, usedPercent=value), self.now)
