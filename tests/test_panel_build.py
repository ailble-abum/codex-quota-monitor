import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('panel_build', Path(__file__).parents[1] / 'tools/build_panel.py')
panel_build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel_build)


class PanelBuildTests(unittest.TestCase):
    def test_build_does_not_depend_on_frozen_renderer_or_feedback(self):
        source = (Path(__file__).parents[1] / 'tools/build_panel.py').read_text()
        self.assertNotIn('context_token_injector.py', source)
        self.assertNotIn('companion_feedback.py', source)
        self.assertIn("'panel_shell.js'", source)

    def test_repository_artwork_is_complete(self):
        art, expressions = panel_build.artwork()
        self.assertEqual(set(art), {'candy', 'cat', 'corgi', 'frost', 'mint', 'tea'})
        self.assertEqual(set(expressions['cat']), {'idle', 'happy', 'concerned', 'notice', 'waiting', 'pet'})
        self.assertTrue(all(value.startswith('data:image/webp;base64,') for value in art.values()))

    def test_shell_owns_remaining_runtime_entry_points(self):
        shell = (Path(__file__).parents[1] / 'quota_monitor/panel_shell.js').read_text()
        for name in ('applyHud', 'positionRetainedHint', 'updateHudTitle'):
            self.assertIn('function ' + name + '(', shell)
        self.assertTrue(shell.startswith('// V2-owned renderer shell.'))


if __name__ == '__main__':
    unittest.main()
