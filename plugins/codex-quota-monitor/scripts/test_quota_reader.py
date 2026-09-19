import unittest
from quota_reader import normalize, normalize_usage


class QuotaTests(unittest.TestCase):
    def test_named_bucket_wins_and_zero_is_valid(self):
        value = normalize({'rateLimits': {'primary': {'usedPercent': 99}},
            'rateLimitsByLimitId': {'codex': {'primary': {'usedPercent': 0, 'windowDurationMins': 300},
                                            'secondary': {'usedPercent': 100}}}})
        self.assertEqual([x['remaining'] for x in value['windows']], [100, 0])

    def test_missing_and_nonfinite_are_not_zero(self):
        for invalid in (None, {}, {'usedPercent': None}, {'usedPercent': float('nan')}, {'usedPercent': True}):
            with self.assertRaises(ValueError):
                normalize({'rateLimits': {'primary': invalid}})

    def test_clamp(self):
        self.assertEqual(normalize({'rateLimits': {'primary': {'usedPercent': 110}}})['windows'][0]['remaining'], 0)

    def test_no_identity_or_credentials_in_output(self):
        result = normalize({'accountId':'private', 'rateLimits': {'primary': {'usedPercent': 20}}})
        self.assertNotIn('private', str(result))

    def test_weekly_only_is_not_promoted_to_five_hours(self):
        result=normalize({'rateLimits':{'primary':None,'secondary':{'usedPercent':22,'windowDurationMins':10080}}})
        self.assertEqual(len(result['windows']),1)
        self.assertEqual(result['windows'][0]['key'],'secondary')
        self.assertEqual(result['windows'][0]['duration'],10080)

    def test_no_periodic_window_is_not_unlimited(self):
        result=normalize({'rateLimits':{'limitId':'codex','planType':'test','primary':None,'secondary':None}})
        self.assertEqual(result['windows'],[])
        self.assertEqual(result['windowStatus'],'not_reported')
        self.assertNotIn('unlimited',str(result))

    def test_pace_and_exhaustion_forecast(self):
        # Halfway through a five-hour window, 70% used is 20 points ahead of pace.
        now=10_000
        result=normalize({'rateLimits':{'primary':{'usedPercent':70,'windowDurationMins':300,
            'resetsAt':now+150*60}}},now=now)
        window=result['windows'][0]
        self.assertAlmostEqual(window['paceDelta'],20)
        self.assertLess(window['projectedExhaustAt'],window['resetsAt'])

    def test_usage_summary_is_sanitized_and_bounded(self):
        value=normalize_usage({'summary':{'lifetimeTokens':123,'peakDailyTokens':None},
            'dailyUsageBuckets':[{'startDate':'2026-09-18','tokens':50},{'startDate':3,'tokens':9}]})
        self.assertEqual(value['summary']['lifetimeTokens'],123)
        self.assertIsNone(value['summary']['peakDailyTokens'])
        self.assertEqual(value['dailyUsageBuckets'],[{'startDate':'2026-09-18','tokens':50}])

    def test_reset_credits_expose_count_and_expiry_not_ids(self):
        value=normalize({'rateLimits':{'primary':{'usedPercent':1}},'rateLimitResetCredits':{
            'availableCount':2,'credits':[{'id':'secret-id','status':'available','expiresAt':20},
                                          {'id':'other','status':'used','expiresAt':10}]}})
        self.assertEqual(value['resetCredits'],{'availableCount':2,'nextExpiresAt':20})
        self.assertNotIn('secret-id',str(value))


if __name__ == '__main__':
    unittest.main()
