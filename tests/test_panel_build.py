import importlib.util
import hashlib
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
        self.assertEqual(set(expressions), set(art))
        self.assertTrue(all(set(frames) == {'idle', 'happy', 'concerned', 'notice', 'waiting', 'pet'}
                            for frames in expressions.values()))
        self.assertTrue(all(value.startswith('data:image/webp;base64,') for value in art.values()))

    def test_repository_artwork_has_reproducible_manifest(self):
        hashes = panel_build.resource_hashes()
        self.assertEqual(len(hashes), 42)
        self.assertEqual(set(hashes), {
            f'assets/companions/web/{skin}.webp' for skin in ('candy', 'cat', 'corgi', 'frost', 'mint', 'tea')
        } | {
            f'assets/companions/expressions/{skin}-{name}.webp'
            for skin in ('candy', 'cat', 'corgi', 'frost', 'mint', 'tea')
            for name in ('idle', 'happy', 'concerned', 'notice', 'waiting', 'pet')})
        self.assertTrue(all(len(value) == 64 for value in hashes.values()))

    def test_nova_replaces_the_archived_cat_pixels(self):
        root = Path(__file__).parents[1] / 'assets/companions'
        self.assertEqual(hashlib.sha256((root / 'sources/nova-atlas.png').read_bytes()).hexdigest(),
                         'e7690812503f47b6916f1fed22999843bd744ea7b6a79295899c282d77183e0e')
        self.assertEqual(hashlib.sha256((root / 'sources/nova-notice.png').read_bytes()).hexdigest(),
                         'ca99d508dd9b3787c12f6724ed6a4d8ab9f253bb40f79f20cc46626fb087ab59')
        hashes = panel_build.resource_hashes()
        self.assertNotEqual(hashes['assets/companions/web/cat.webp'],
                            'd2a93051be5be8f4ee215d142d73dc3745b1c1acac77ef4f890b10b0a6987814')
        self.assertNotEqual(hashes['assets/companions/expressions/cat-notice.webp'],
                            'a5d4c30ca4eace725471fd775af51b4176430f8e9e0b9da303d0b41272825176')
        self.assertEqual(len({hashes['assets/companions/expressions/cat-' + name + '.webp']
                              for name in ('idle', 'happy', 'concerned', 'notice', 'waiting', 'pet')}), 6)

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
        self.assertIn('[data-edge="right"] [data-gauge] { left:-7px; }', styles)
        self.assertIn('[data-skin="tea"] { --cti-gauge-left:5.9px; --cti-gauge-right:-7px; }', styles)
        self.assertIn('left:calc(var(--cti-gauge-left,-7px) - 4px)', styles)
        self.assertIn('[data-panel-revealed="true"] [data-gauge]', styles)
        self.assertIn('opacity:0; transform:translateY(-50%) scaleX(0)', styles)
        self.assertIn('[data-gauge] { transition:none; }', styles)
        self.assertIn('overflow-x:hidden; overflow-y:auto', styles)
        self.assertIn('zoom:var(--cti-scale,1)', styles)
        self.assertIn('background:linear-gradient(135deg,transparent 60%', styles)

    def test_compact_bar_prioritizes_percent_and_post_compaction_percent(self):
        root = Path(__file__).parents[1] / 'quota_monitor'
        shell = (root / 'panel_shell.js').read_text()
        geometry = (root / 'panel_geometry.js').read_text()
        styles = (root / 'panel_styles.js').read_text()
        self.assertIn("cell(windowLabel(item, true), item.remaining", shell)
        self.assertIn("windowBudgetText(item)", shell)
        self.assertIn("health?.afterPercent", shell)
        self.assertIn("${chinese ? '压后' : 'after'} ${afterPercent}", shell)
        self.assertNotIn("health.after == null ? '…' : token(health.after)", shell)
        self.assertIn("* 70", geometry)
        self.assertIn("align-self:stretch; justify-content:center", styles)
        self.assertIn("align-self:center; font-size:0; line-height:0; position:relative", styles)
        self.assertIn("transform:translate(-50%,-50%)", styles)
        probe = (Path(__file__).parents[1] / 'tools/verify_compact_hud.cjs').read_text()
        for evidence in ("['62%', '37%']", "['约 8.8h', '↻3 · 压后 20.2%']", 'unknown-scaled.png'):
            self.assertIn(evidence, probe)

    def test_companion_size_slider_has_a_visible_track(self):
        styles = (Path(__file__).parents[1] / 'quota_monitor/panel_styles.js').read_text()
        self.assertIn('[data-mascot-scale]::-webkit-slider-runnable-track', styles)
        self.assertIn('[data-mascot-scale]::-moz-range-track', styles)

    def test_drag_does_not_animate_or_write_storage_on_each_move(self):
        root = Path(__file__).parents[1] / 'quota_monitor'
        styles = (root / 'panel_styles.js').read_text()
        layout = (root / 'panel_layout_runtime.js').read_text()
        companion = (root / 'panel_companion_runtime.js').read_text()
        self.assertIn('[data-dragging="true"] { transition:none; }', styles)
        self.assertIn('root.style.left = `${x}px`; root.style.top = `${y}px`', layout)
        self.assertIn('if (gesture.moved) saveLayout(root)', layout)
        self.assertIn('if (gesture.moved && event.type === \'pointercancel\')', companion)
        self.assertIn('} else if (gesture.moved) {\n        saveLayout(root);', companion)
        self.assertNotIn('saveLayout(root); applyStoredHudPosition(root)', companion)

    def test_dock_auto_hide_restores_compact_mode_and_respects_focus(self):
        root = Path(__file__).parents[1] / 'quota_monitor'
        layout = (root / 'panel_layout_runtime.js').read_text()
        geometry = (root / 'panel_geometry.js').read_text()
        self.assertIn("root.dataset.collapsed = 'true'", layout)
        self.assertIn("localStorage.setItem(COLLAPSE_KEY, 'true')", layout)
        self.assertIn("if (root.dataset.docked !== 'true' || root.dataset.dockPinned === 'true') return", layout)
        self.assertIn("if (root.dataset.docked !== 'true') return", layout)
        self.assertIn("focused?.matches?.(':focus-visible')", layout)
        self.assertIn("root.addEventListener('focusin'", layout)
        self.assertIn("root.addEventListener('focusout'", layout)
        self.assertIn('compactDockPanelY(mascotY, mascotHeight, rect.height)', layout)
        self.assertIn('compact ? 0 : mascotHeight', layout)
        self.assertIn('function compactDockPanelY(', geometry)

    def test_compact_bar_hover_prefers_time_budget(self):
        shell = (Path(__file__).parents[1] / 'quota_monitor/panel_shell.js').read_text()
        self.assertIn('const hoverBudget = windows.map', shell)
        self.assertIn('windowBudgetText(item)', shell)

    def test_refresh_button_requests_account_refresh(self):
        mount = (Path(__file__).parents[1] / 'quota_monitor/panel_mount.js').read_text()
        bridge = (Path(__file__).parents[1] / 'quota_monitor/page_bridge.js').read_text()
        self.assertIn('window.__quotaMonitorV2RefreshRequested = true', mount)
        self.assertIn("options.action === 'refresh'", bridge)


if __name__ == '__main__':
    unittest.main()
