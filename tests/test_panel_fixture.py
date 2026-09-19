import tempfile
import unittest
from pathlib import Path

from tools.panel_fixture import fixtures, literal, renderer


class PanelFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_legacy_modules_are_never_executed(self):
        (self.root / 'context_token_injector.py').write_text(
            'raise RuntimeError("must not execute")\n'
            'INJECTION_SCRIPT = "__COMPANION_FEEDBACK__ __COMPANION_ART__ __COMPANION_EXPRESSIONS__"\n')
        for filename, name, value in (
                ('companion_feedback.py', 'COMPANION_FEEDBACK_JS', 'feedback'),
                ('companion_art.py', 'COMPANION_ART', {'cat': 'data:synthetic'}),
                ('companion_expressions.py', 'COMPANION_EXPRESSIONS', {'idle': {}})):
            (self.root / filename).write_text(
                'raise RuntimeError("must not execute")\n' + name + ': object = ' + repr(value))
        self.assertEqual(renderer(self.root), 'feedback {"cat": "data:synthetic"} {"idle": {}}')

    def test_nonliteral_source_is_rejected(self):
        path = self.root / 'dynamic.py'
        path.write_text('VALUE = dict(secret="unexecuted")')
        with self.assertRaises(ValueError):
            literal(path, 'VALUE')

    def test_missing_constant_fails_explicitly(self):
        path = self.root / 'empty.py'
        path.write_text('')
        with self.assertRaises(ValueError):
            literal(path, 'VALUE')

    def test_fixtures_use_new_pipeline_and_distinct_task_numbers(self):
        payloads = fixtures()
        self.assertEqual(payloads['one']['summaries'][0]['latest_context_percent'], 25)
        self.assertEqual(payloads['two']['summaries'][0]['session_total_tokens'], 900)
        self.assertEqual(payloads['missing']['summaries'], [])
        self.assertIn('observedAt', payloads['one'])
