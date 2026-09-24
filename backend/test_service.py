import unittest, tempfile, json, time
from datetime import datetime, timezone
from pathlib import Path
import service as s

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        s.DB = str(Path(self.tmp.name) / 'test.sqlite')
        s.init()
        self.stamp = s.now()
    def tearDown(self):
        self.tmp.cleanup()
    def payload(self, value=400, channel='wind', stamp=None):
        return json.dumps({'source':'SANSA','measurements':[{'id':channel,'unit':s.CHANNELS[channel][1],
          'value':value,'observedAt':stamp or self.stamp}]}).encode()
    def put(self, body):
        return s.ingest('https://test.invalid/fixture',body)
    def test_empty_state_has_no_indices(self):
        result=s.snapshot()
        self.assertIsNone(result['speedEnergyIndex'])
        self.assertTrue(all(m['health']=='unavailable' for m in result['measurements']))
    def test_repeated_poll_does_not_fabricate_history(self):
        self.put(self.payload()); self.put(self.payload())
        self.assertEqual(len(s.snapshot()['measurements'][0]['history']),1)
        self.assertEqual(len(s.snapshot()['attempts']),2)
    def test_conflict_preserves_original_and_excludes_scoring(self):
        self.put(self.payload()); self.assertEqual(self.put(self.payload(500)),'conflict')
        result=s.snapshot()
        self.assertEqual(result['measurements'][0]['health'],'conflict')
        self.assertEqual(result['measurements'][0]['value'],400)
        self.assertIsNone(result['measurements'][0]['history'][0]['value'])
        self.assertIsNone(result['speedEnergyIndex'])
    def test_invalid_payload_retained(self):
        for body in (b'[]',b'bad json',b'{"source":"SANSA","measurements":[null]}'):
            self.assertEqual(self.put(body),'rejected')
        with s.connection() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM payloads').fetchone()[0],3)
    def test_stale_sample(self):
        stamp=datetime.fromtimestamp(time.time()-s.STALE-10,timezone.utc).isoformat()
        self.put(self.payload(stamp=stamp))
        self.assertEqual(s.snapshot()['measurements'][0]['health'],'stale')
    def test_missing_does_not_carry_forward_value(self):
        old=datetime.fromtimestamp(time.time()-60,timezone.utc).isoformat()
        self.put(self.payload(stamp=old));self.put(self.payload(None))
        self.assertEqual(s.snapshot()['measurements'][0]['health'],'missing')
        self.assertIsNone(s.snapshot()['measurements'][0]['value'])
    def test_aligned_indices_only(self):
        self.put(self.payload()); self.put(self.payload(-5,'bz'))
        self.assertEqual(s.snapshot()['speedEnergyIndex'],1)
        other=datetime.fromtimestamp(time.time()-60,timezone.utc).isoformat()
        with s.connection() as c:c.execute("DELETE FROM observations WHERE channel='bz'")
        self.put(self.payload(-5,'bz',other))
        self.assertIsNone(s.snapshot()['speedEnergyIndex'])
    def test_api_health_distinguishes_freshness(self):
        statuses=[]
        for path in ('/healthz','/readyz'):
            s.app({'PATH_INFO':path,'REQUEST_METHOD':'GET'},lambda status,headers:statuses.append(status))
        self.assertEqual(statuses,['200 OK','503 Service Unavailable'])
    def test_source_and_naive_time_rejected(self):
        self.assertEqual(self.put(self.payload().replace(b'SANSA',b'OTHER')),'rejected')
        self.assertEqual(self.put(self.payload(stamp='2026-01-01T00:00:00')),'rejected')

if __name__=='__main__': unittest.main()
