import json
import tempfile
import unittest
from pathlib import Path

from context_token_inspector import summarize_session, summarize_session_fast
from context_token_injector import INJECTION_SCRIPT, build_payload


class InspectorTests(unittest.TestCase):
    def test_edge_docking_and_all_companion_skins_are_bundled(self):
        self.assertIn("function dockCandidate", INJECTION_SCRIPT)
        self.assertIn("distance<=14", INJECTION_SCRIPT)
        self.assertIn("setTimeout(()=>", INJECTION_SCRIPT)
        for skin in ("candy", "corgi", "mint", "frost", "tea"):
            self.assertIn(f"{skin}:", INJECTION_SCRIPT)

    def test_latest_model_and_effort_are_reported(self):
        rows = [
            {'type':'session_meta','payload':{'id':'thread','cwd':'/tmp'}},
            {'type':'turn_context','payload':{'model':'old','effort':'low'}},
            {'type':'turn_context','payload':{'model':'gpt-test','effort':'high'}},
            {'type':'event_msg','timestamp':'2026-01-01T00:00:00Z','payload':{'type':'token_count','info':{
                'last_token_usage':{'input_tokens':10,'total_tokens':12},
                'total_token_usage':{'total_tokens':12},'model_context_window':100}}},
        ]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'session.jsonl'
            path.write_text('\n'.join(json.dumps(row) for row in rows))
            for summary in (summarize_session(path),summarize_session_fast(path)):
                self.assertEqual(summary['model'],'gpt-test')
                self.assertEqual(summary['reasoning_effort'],'high')
            payload=build_payload([folder],10,'thread')
            self.assertEqual(payload['summaries'][0]['model'],'gpt-test')
            self.assertEqual(payload['summaries'][0]['reasoning_effort'],'high')


if __name__ == '__main__':
    unittest.main()
