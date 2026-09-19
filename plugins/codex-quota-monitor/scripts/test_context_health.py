import json
import tempfile
import unittest
from pathlib import Path
from context_health import scan
from usage_history import History, recent_breakdown


class HealthTests(unittest.TestCase):
    def test_compression_is_not_cumulative_tokens(self):
        def usage(n,total):return {'type':'event_msg','payload':{'type':'token_count','info':{'last_token_usage':{'input_tokens':n},'total_token_usage':{'total_tokens':total},'model_context_window':258400}}}
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'test.jsonl'
            rows=[usage(220000,5000000),{'type':'compacted','payload':{}},usage(10000,5010000)]
            p.write_text('\n'.join(map(json.dumps,rows)))
            result=scan(p)
            self.assertEqual(result['count'],1)
            self.assertEqual(result['after'],10000)
            self.assertFalse(result['recommendHandoff'])
            rows += [{'type':'compacted','payload':{}},usage(110000,5120000)]
            p.write_text('\n'.join(map(json.dumps,rows)))
            self.assertTrue(scan(p)['recommendHandoff'])

    def test_pending_is_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'test.jsonl';p.write_text(json.dumps({'type':'compacted','payload':{}}))
            self.assertIsNone(scan(p)['after'])

    def test_history_empty_and_resets(self):
        page=History.page([])
        self.assertIn('0 个采样点',page)
        rows=[{'at':1,'windows':[{'key':'primary','remaining':5,'resetsAt':2}]},
              {'at':3,'windows':[{'key':'primary','remaining':99,'resetsAt':4}]}]
        self.assertEqual(History.page(rows).count('<polyline'),2)

    def test_history_adds_context_and_cache_trends_when_recorded(self):
        rows=[
            {'at':1,'windows':[],'context':{'latest_context_percent':25,'latest_turn_input_tokens':100,'latest_turn_cached_input_tokens':50}},
            {'at':3,'windows':[],'context':{'latest_context_percent':80,'latest_turn_input_tokens':200,'latest_turn_cached_input_tokens':100}},
        ]
        page=History.page(rows)
        self.assertIn('上下文占用趋势',page)
        self.assertIn('缓存输入占比趋势',page)
        self.assertEqual(page.count('<polyline'),2)

    def test_recent_breakdown_groups_models_and_project_names(self):
        value=recent_breakdown([
            {'model':'gpt-a','cwd':'/work/alpha','session_total_tokens':100},
            {'model':'gpt-a','cwd':'/work/beta','session_total_tokens':50},
            {'model':'gpt-b','cwd':'/work/alpha','session_total_tokens':25},
        ])
        self.assertEqual(value['models'][0],('gpt-a',150))
        self.assertEqual(value['projects'][0],('alpha',125))
        page=History.page([{'at':1,'windows':[],'breakdown':value}])
        self.assertIn('最近会话按模型',page)
        self.assertIn('最近会话按项目',page)


if __name__=='__main__':unittest.main()
