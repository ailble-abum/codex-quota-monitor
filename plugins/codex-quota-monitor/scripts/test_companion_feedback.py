"""Execute the shipped pure JS reducer; no account or session fixtures."""
import unittest
from test_context_token_inspector import run_js
from pathlib import Path


class FeedbackTests(unittest.TestCase):
    def run_case(self, code):
        path = Path(__file__).with_name('companion_feedback.py')
        self.assertTrue(path.exists(), 'companion feedback reducer is not implemented')
        from companion_feedback import COMPANION_FEEDBACK_JS
        return run_js(COMPANION_FEEDBACK_JS, '(()=>{' + code + '})()')

    def test_quota_thresholds_deduplicate_and_recover_only_on_live_read(self):
        self.assertEqual(self.run_case('''
          let s={}; const feed=(n,live=true)=>{const r=companionStep(s,{account:'a',cycle:'c',live,remaining:n,thread:'t',ctx:20},1000);s=r.state;return r.event;};
          return [feed(50),feed(20),feed(19),feed(10),feed(0),feed(90,false),feed(90)];
        '''), [None,'quota-watch',None,'quota-low','quota-empty',None,'quota-restored'])

    def test_context_switch_never_carries_previous_task_or_repeats_alert(self):
        self.assertEqual(self.run_case('''
          let s={}; const feed=(thread,ctx)=>{let r=companionStep(s,{account:'a',cycle:'c',live:true,remaining:80,thread,ctx},1000);s=r.state;return [r.event,r.ctxLevel];};
          return [feed('a',86),feed('b',20),feed('a',86),feed('a',96),feed(null,99)];
        '''), [['ctx-high',2],[None,0],[None,2],['ctx-critical',3],[None,0]])

    def test_unknown_values_and_account_switch_do_not_fake_recovery(self):
        self.assertEqual(self.run_case('''
          let s={};const feed=x=>{let r=companionStep(s,{thread:null,ctx:null,...x},1000);s=r.state;return [r.event,r.quotaLevel];};
          return [feed({account:'a',cycle:'c',live:true,remaining:0}),feed({account:'b',cycle:'c',live:true,remaining:80}),feed({account:'b',cycle:'c',live:true,remaining:null}),feed({account:'b',cycle:'c',live:false,remaining:0})];
        '''), [['quota-empty',3],[None,0],[None,None],[None,None]])

    def test_simultaneous_alerts_merge_and_context_is_rearmed_after_clear_drop(self):
        self.assertEqual(self.run_case('''
          let s={};const feed=ctx=>{let r=companionStep(s,{account:'a',cycle:'c',live:true,remaining:8,thread:'a',ctx},1000);s=r.state;return r.event;};
          return [feed(96),feed(94),feed(96),feed(50),feed(96)];
        '''), ['quota-low+ctx-critical',None,None,None,None])

    def test_confirmed_compaction_only_new_event_on_same_thread(self):
        self.assertEqual(self.run_case('''
          let s={};const feed=(thread,compaction)=>{let r=companionStep(s,{account:'a',live:true,remaining:80,thread,ctx:30,compaction},1000);s=r.state;return r.event;};
          return [feed('a','old'),feed('a','new'),feed('a','new'),feed('b','other')];
        '''), [None,'compacted',None,None])

    def test_unrelated_window_reset_and_account_roundtrip_do_not_repeat(self):
        self.assertEqual(self.run_case("""
          let s={};const feed=(account,reset)=>{let r=companionStep(s,{account,live:true,remaining:8,windows:[{key:'week',resetsAt:900,remaining:8},{key:'short',resetsAt:reset,remaining:80}]},1000);s=r.state;return r.event;};
          return [feed('a',100),feed('a',200),feed('b',200),feed('a',200)];
        """), ['quota-low',None,'quota-low',None])

    def test_health_identity_is_not_mutable_active_id(self):
        self.assertEqual(self.run_case("""
          const p={activeThreadId:'b',healthThreadId:'a',health:{latestAt:'a-event'}};
          return [companionHealth(p,'b'),companionHealth(p,'local:a'),companionHealth(p,null)];
        """), [None,{'latestAt':'a-event'},None])

    def test_expression_returns_to_persistent_warning_after_touch(self):
        self.assertEqual(self.run_case("""
          return [companionExpression('pet','waiting'),companionExpression(null,'waiting'),companionExpression('happy','idle'),companionExpression(null,'unknown')];
        """), ['pet','waiting','happy','concerned'])

    def test_missing_account_identity_deduplicates_block_but_never_confirms_recovery(self):
        self.assertEqual(self.run_case("""
          let s={}; const feed=blocked=>{let r=companionStep(s,{account:null,live:true,blocked,remaining:80},1000);s=r.state;return r.event;};
          return [feed(true),feed(true),feed(false)];
        """), ['quota-empty',None,None])

    def test_failed_read_does_not_erase_identity_for_later_confirmed_recovery(self):
        self.assertEqual(self.run_case("""
          let s={};const feed=x=>{const r=companionStep(s,x,1000);s=r.state;return r.event;};
          return [feed({account:'a',live:true,remaining:0}),feed({account:null,live:false}),feed({account:'a',live:true,remaining:80})];
        """), ['quota-empty',None,'quota-restored'])

    def test_pet_gesture_requires_head_hold_and_never_steals_body_drag(self):
        self.assertEqual(self.run_case('''
          return [companionGesture({head:true,x:0,y:0,at:0},3,2,500),companionGesture({head:false,x:0,y:0,at:0},3,9,500),companionGesture({head:true,x:0,y:0,at:0},0,20,100),companionGesture({head:true,x:0,y:0,at:0},0,0,100)];
        '''), ['pet','drag','drag','click'])
