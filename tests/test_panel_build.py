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

    def test_host_detail_projection_is_repository_owned_and_observer_free(self):
        source = (Path(__file__).parents[1] / 'tools/build_panel.py').read_text()
        module = (Path(__file__).parents[1] / 'quota_monitor/panel_host_details.js').read_text()
        self.assertIn("'panel_host_details.js'", source)
        self.assertIn('function projectHostDetails(', module)
        self.assertIn('function disposeHostDetails(', module)
        self.assertNotIn('MutationObserver', module)
        for name in ('applySidebar', 'applyFooters', 'assistantNodes', 'detailForVisiblePage'):
            self.assertNotIn('function ' + name + '(', module)

    def test_local_samples_projection_is_repository_owned(self):
        source = (Path(__file__).parents[1] / 'tools/build_panel.py').read_text()
        module = (Path(__file__).parents[1] / 'quota_monitor/panel_samples.js').read_text()
        self.assertIn("'panel_samples.js'", source)
        self.assertIn('function renderLocalSamples(', module)
        self.assertNotIn('panel_history.js', source)
        self.assertNotIn('session.jsonl', module)

    def test_compact_bar_keeps_original_battery_visual(self):
        styles = (Path(__file__).parents[1] / 'quota_monitor/panel_styles.js').read_text()
        self.assertIn('width:max-content; overflow:hidden', styles)
        self.assertIn('background:color-mix(in srgb,var(--cti-tone) 15%,transparent)', styles)
        self.assertIn('width:9px; height:30px', styles)
        self.assertIn('background:var(--cti-tone); border-radius:2px', styles)
        self.assertIn('flex-direction:column; gap:4px; width:7px', styles)
        self.assertIn('[data-edge="right"] [data-gauge] { left:-3px; }', styles)
        self.assertIn('overflow-x:hidden; overflow-y:auto', styles)
        self.assertIn('zoom:var(--cti-scale,1)', styles)
        self.assertIn('background:linear-gradient(135deg,transparent 60%', styles)

    def test_compact_bar_hover_prefers_time_budget(self):
        shell = (Path(__file__).parents[1] / 'quota_monitor/panel_shell.js').read_text()
        self.assertIn('const hoverBudget = windows.map', shell)
        self.assertIn('windowBudgetText(item)', shell)


if __name__ == '__main__':
    unittest.main()
