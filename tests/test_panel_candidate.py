import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('candidate', Path(__file__).parents[1] / 'tools/build_panel_candidate.py')
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


class CandidateTests(unittest.TestCase):
    def test_unrecognized_input_fails_before_any_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'context_token_injector.py').write_text('raise RuntimeError("must never execute")')
            with self.assertRaises(ValueError):
                candidate.build(root)

    def test_unknown_or_duplicated_boundaries_are_rejected(self):
        for source in ('no markers', 'begin one end begin two end'):
            with self.assertRaises(ValueError):
                candidate.cut(source, 'begin', 'end')

    def test_css_cleanup_scopes_attributes_without_changing_specificity(self):
        css = '`unused badge\n      .cti-hud {\n color:CanvasText; }\n'
        css += '\n'.join('      [data-probe%d] { display:block; }' % i for i in range(11))
        css += '\n      [data-details] summary, [data-skins] summary { cursor:pointer; }\n'
        css += '      .cti-reply-footer { unused footer }`'
        result = candidate.panel_css(css)
        self.assertNotIn('unused', result)
        self.assertEqual(result.count(':where(#codex-context-token-inspector-root)'), 13)
        self.assertIn('color:CanvasText', result)
        self.assertIn(', :where(#codex-context-token-inspector-root) [data-skins]', result)
        with self.assertRaises(ValueError):
            candidate.panel_css(css.replace('[data-probe0]', '.other'))
        with self.assertRaises(ValueError):
            candidate.panel_css('unknown template')

    def test_metrics_module_replaces_old_definitions(self):
        source = (Path(__file__).parents[1] / 'tools/build_panel_candidate.py').read_text()
        self.assertIn("(assets / 'panel_metrics.js').read_text()", source)
        for name in ('tr', 'quotaTone'):
            self.assertIn("script = cut(script, '  function %s(" % name, source)

    def test_geometry_module_replaces_old_definitions(self):
        source = (Path(__file__).parents[1] / 'tools/build_panel_candidate.py').read_text()
        self.assertIn("(assets / 'panel_geometry.js').read_text()", source)
        for name in ('hudMode', 'dockSafeTop', 'dockVerticalY', 'dockCandidate',
                     'presetWidth', 'resizeGeometry', 'contextHintGeometry'):
            self.assertIn("script = cut(script, '  function %s(" % name, source)

    def test_layout_runtime_replaces_stateful_old_definitions(self):
        source = (Path(__file__).parents[1] / 'tools/build_panel_candidate.py').read_text()
        self.assertIn("(assets / 'panel_layout_runtime.js').read_text()", source)
        for name in ('clearDockHide', 'scheduleDockHide', 'revealDock', 'undockHud',
                     'applyDockPosition', 'applyStoredHudPosition', 'syncExpandedAnchor',
                     'setLayoutPreset', 'installHudDrag', 'keepTogglePosition', 'clampHud'):
            self.assertIn("script = cut(script, '  function %s(" % name, source)

    def test_header_template_is_not_extracted_from_old_renderer(self):
        source = (Path(__file__).parents[1] / 'tools/build_panel_candidate.py').read_text()
        self.assertIn("(assets / 'panel_templates.js').read_text()", source)
        self.assertIn("(assets / 'panel_styles.js').read_text()", source)
        self.assertNotIn("template('ensureHud', 'root.innerHTML')", source)
        self.assertNotIn("template('applyHud', 'body.innerHTML')", source)
        self.assertNotIn("panel_css(template('ensureStyle', 'const css'))", source)

    def test_companion_view_replaces_old_assembly(self):
        source = (Path(__file__).parents[1] / 'tools/build_panel_candidate.py').read_text()
        self.assertIn("(assets / 'panel_companion_view.js').read_text()", source)
        self.assertIn("script = cut(script, '  function mascotSvg('", source)
        self.assertIn("script = cut(script, '  function applyMascotSkin('", source)

    def test_companion_behavior_is_not_loaded_from_frozen_source(self):
        source = (Path(__file__).parents[1] / 'tools/build_panel_candidate.py').read_text()
        self.assertIn("(assets / 'panel_companion_behavior.js').read_text()", source)
        self.assertNotIn("'COMPANION_FEEDBACK_JS'", source)

    def test_companion_runtime_replaces_old_dom_handlers(self):
        source = (Path(__file__).parents[1] / 'tools/build_panel_candidate.py').read_text()
        self.assertIn("(assets / 'panel_companion_runtime.js').read_text()", source)
        for name in ('createRetainedMascot', 'applyCompanionExpression', 'companionReact',
                     'applyCompanionFeedback'):
            self.assertIn("script = cut(script, '  function %s(" % name, source)
