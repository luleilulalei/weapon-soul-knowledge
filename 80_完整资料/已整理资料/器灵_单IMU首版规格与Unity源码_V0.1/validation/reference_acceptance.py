#!/usr/bin/env python3
"""Independent executable acceptance oracle. NOT a C# interpreter or Unity test.
Checks event-gate and charge rules in Python, plus delivered CSV structure.
Actual C# behavior must separately pass CoreSelfTest in Unity.
"""
import csv, math, pathlib, unittest
from dataclasses import dataclass, field

@dataclass
class Gate:
    session: str = 'attempt-1'
    window: str = 'opening-1'
    opened: int = 1000
    closed: int = 4500
    running: bool = True
    connected: bool = True
    charging: bool = False
    docked: bool = False
    calibrated: bool = True
    seen: set = field(default_factory=set)
    charge_start: int | None = None
    ready: bool = False
    hits: int = 0
    def clear(self): self.charge_start=None; self.ready=False
    def pause(self): self.running=False; self.calibrated=False; self.clear()
    def submit(self, action, stamp, now, event='e', session='attempt-1', window='opening-1'):
        if not self.running: return False
        if not self.connected or self.charging or self.docked:
            self.pause(); return False
        if session != self.session or window != self.window: return False
        if not event or event in self.seen: return False
        self.seen.add(event)
        if stamp>now or now-stamp>250 or stamp<self.opened or stamp>=self.closed or now>=self.closed: return False
        if action in ('Cancel','Neutral','GuardExit','LeftSlash','RightSlash'):
            self.clear(); return True
        if action=='ChargeStart': self.clear(); self.charge_start=stamp
        if action=='ChargeReady':
            if self.charge_start is None or stamp-self.charge_start<800: return False
            self.ready=True
        if action=='DownSlash':
            self.hits+=int(self.ready); self.clear()
        return True

@dataclass
class ReleaseGate:
    """Independent expected release-transition contract; threshold configured by test."""
    ready: bool = False
    pending_at: int | None = None
    timeout: int = 300
    def feed(self, action, t):
        if self.pending_at is not None and t-self.pending_at >= self.timeout:
            self.ready=False; self.pending_at=None; return 'cancel'
        if action in ('cancel','pause','disconnect','new_window','left','right','reverse','return_up'):
            self.ready=False; self.pending_at=None; return 'cancel'
        if action=='leave':
            if not self.ready: return 'cancel'
            if self.pending_at is None: self.pending_at=t
        if action=='down':
            hit=self.ready; self.ready=False; self.pending_at=None
            return 'hit' if hit else 'miss'
        return 'pending' if self.pending_at is not None else 'holding'

class Acceptance(unittest.TestCase):
    def test_release_pending_within_window(self):
        g=ReleaseGate(ready=True); self.assertEqual(g.feed('leave',1000),'pending'); self.assertEqual(g.feed('down',1299),'hit')
    def test_release_timeout_precedes_down(self):
        g=ReleaseGate(ready=True); g.feed('leave',1000); self.assertEqual(g.feed('down',1300),'cancel'); self.assertEqual(g.feed('down',1301),'miss')
    def test_release_before_ready(self):
        g=ReleaseGate(); self.assertEqual(g.feed('leave',1000),'cancel'); self.assertEqual(g.feed('down',1100),'miss')
    def test_release_interrupts(self):
        for action in ('cancel','pause','disconnect','new_window','left','right','reverse','return_up'):
            with self.subTest(action=action):
                g=ReleaseGate(ready=True);g.feed('leave',1000);g.feed(action,1100);self.assertEqual(g.feed('down',1200),'miss')

    def test_duplicate(self):
        g=Gate(); self.assertTrue(g.submit('ChargeStart',1000,1000)); self.assertFalse(g.submit('ChargeStart',1000,1000))
    def test_missing_id(self): self.assertFalse(Gate().submit('ChargeStart',1000,1000,event=''))
    def test_old_session(self): self.assertFalse(Gate().submit('ChargeStart',1000,1000,session='attempt-0'))
    def test_old_window(self): self.assertFalse(Gate().submit('ChargeStart',1000,1000,window='opening-0'))
    def test_age_boundary(self):
        self.assertTrue(Gate().submit('ChargeStart',1000,1250)); self.assertFalse(Gate().submit('ChargeStart',1000,1251))
    def test_future(self): self.assertFalse(Gate().submit('ChargeStart',1001,1000))
    def test_half_open_window(self):
        self.assertFalse(Gate().submit('ChargeStart',999,1000)); self.assertFalse(Gate().submit('ChargeStart',4500,4500)); self.assertFalse(Gate().submit('ChargeStart',4499,4500)); self.assertTrue(Gate().submit('ChargeStart',4499,4499))
    def test_ready_requires_start(self): self.assertFalse(Gate().submit('ChargeReady',2000,2000))
    def test_charge_threshold(self):
        g=Gate(); g.submit('ChargeStart',1000,1000); self.assertFalse(g.submit('ChargeReady',1799,1799,event='2')); self.assertTrue(g.submit('ChargeReady',1800,1800,event='3'))
    def test_charge_consumed_once(self):
        g=Gate(); g.submit('ChargeStart',1000,1000); g.submit('ChargeReady',1800,1800,event='2'); g.submit('DownSlash',1900,1900,event='3'); g.submit('DownSlash',2000,2000,event='4'); self.assertEqual(g.hits,1)
    def test_cancellation_variants(self):
        for action in ('Cancel','Neutral','GuardExit','LeftSlash','RightSlash'):
            with self.subTest(action=action):
                g=Gate(); g.submit('ChargeStart',1000,1000); g.submit('ChargeReady',1800,1800,event='2'); g.submit(action,1900,1900,event='3'); g.submit('DownSlash',2000,2000,event='4'); self.assertEqual(g.hits,0)
    def test_restart_charge_clears_ready(self):
        g=Gate(); g.submit('ChargeStart',1000,1000); g.submit('ChargeReady',1800,1800,event='2'); g.submit('ChargeStart',1900,1900,event='3'); g.submit('DownSlash',2000,2000,event='4'); self.assertEqual(g.hits,0)
    def test_pause_invalidates(self):
        g=Gate(); g.submit('ChargeStart',1000,1000); g.pause(); self.assertFalse(g.calibrated); self.assertFalse(g.submit('ChargeReady',1800,1800,event='2'))
    def test_device_interlocks(self):
        for attr,val in [('connected',False),('charging',True),('docked',True)]:
            with self.subTest(attr=attr):
                g=Gate(); setattr(g,attr,val); self.assertFalse(g.submit('ChargeStart',1000,1000)); self.assertFalse(g.running); self.assertFalse(g.calibrated)
    def test_raw_candidate_margins(self):
        # Candidate only: not a physical direction or motion-accuracy assertion.
        def dominant(x,y,z): return x>120 and abs(x)>1.4*abs(y) and abs(x)>1.4*abs(z)
        self.assertFalse(dominant(120,0,0)); self.assertTrue(dominant(121,0,0)); self.assertFalse(dominant(140,100,0)); self.assertTrue(dominant(141,100,0))
    def test_delivered_csv(self):
        root=pathlib.Path(__file__).resolve().parents[1]
        paths=list((root/'unity').rglob('*.csv'))
        self.assertTrue(paths,'No delivered raw replay CSV')
        for p in paths:
            with self.subTest(file=p.name), p.open(newline='') as f:
                reader=csv.DictReader(f); self.assertEqual(reader.fieldnames,['sessionId','deviceId','seq','tMs','ax','ay','az','gx','gy','gz','source'])
                rows=list(reader); self.assertGreater(len(rows),0)
                previous=(-1,-1); identity=None
                for r in rows:
                    pair=(int(r['seq']),int(r['tMs'])); self.assertGreater(pair[0],previous[0]); self.assertGreater(pair[1],previous[1]); previous=pair
                    current=(r['sessionId'],r['deviceId']); self.assertTrue(all(current)); identity=identity or current; self.assertEqual(current,identity)
                    self.assertIn(r['source'],('simulated','replay','hardware'))
                    for k in ('ax','ay','az','gx','gy','gz'): self.assertTrue(math.isfinite(float(r[k])))

if __name__=='__main__':
    print('Scope: independent Python rules + CSV checks only; C# compilation, Unity import/runtime and hardware NOT executed.',flush=True)
    unittest.main(verbosity=2)
