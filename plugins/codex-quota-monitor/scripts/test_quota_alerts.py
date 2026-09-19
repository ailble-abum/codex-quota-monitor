import tempfile
import time
import unittest
from pathlib import Path
from quota_alerts import QuotaAlerts, eligible


class AlertTests(unittest.TestCase):
    def quota(self, remaining=10, account='account-a', reset=None):
        return {'status': 'live', 'updatedAt': time.time(), 'accountKey': account,
                'windows': [{'key':'primary','duration':300,'remaining':remaining,'resetsAt':reset or time.time()+5000}]}

    def test_disabled_and_stale_never_notify(self):
        with tempfile.TemporaryDirectory() as directory:
            sent=[]
            reader=QuotaAlerts(Path(directory)/'alerts.json',lambda m: sent.append(m) or True)
            quota=self.quota()
            reader.check(quota)
            quota['updatedAt']-=121
            reader.check(quota,True)
            self.assertEqual(sent,[])

    def test_dedupe_survives_restart_but_new_window_notifies(self):
        with tempfile.TemporaryDirectory() as directory:
            sent=[]
            path=Path(directory)/'alerts.json'
            sender=lambda m: sent.append(m) or True
            quota=self.quota()
            QuotaAlerts(path,sender).check(quota,True)
            QuotaAlerts(path,sender).check(quota,True)
            self.assertEqual(len(sent),1)
            quota['windows'][0]['resetsAt']+=5000
            QuotaAlerts(path,sender).check(quota,True)
            self.assertEqual(len(sent),2)
            quota['accountKey']='account-b'
            QuotaAlerts(path,sender).check(quota,True)
            self.assertEqual(len(sent),3)

    def test_threshold_and_missing_identity(self):
        self.assertEqual(len(eligible(self.quota(20))),1)
        self.assertEqual(eligible(self.quota(20.01)),[])
        self.assertEqual(eligible(self.quota(0,account=None)),[])


if __name__=='__main__':
    unittest.main()
