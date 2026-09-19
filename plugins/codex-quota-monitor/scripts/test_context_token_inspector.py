import json
import tempfile
import unittest
from pathlib import Path

from companion_art import COMPANION_ART
from context_token_inspector import summarize_session, summarize_session_fast
from context_token_injector import INJECTION_SCRIPT, build_payload


def block(start: str, end: str) -> str:
    """Slice of the injected script between two anchors."""
    begin = INJECTION_SCRIPT.index(start)
    return INJECTION_SCRIPT[begin:INJECTION_SCRIPT.index(end, begin)]


class InspectorTests(unittest.TestCase):
    def test_edge_docking_and_all_companion_skins_are_bundled(self):
        self.assertIn("function dockCandidate", INJECTION_SCRIPT)
        self.assertIn("distance<=14", INJECTION_SCRIPT)
        self.assertIn("setTimeout(()=>", INJECTION_SCRIPT)
        # One vector fallback per skin, even for skins that also ship a bitmap.
        self.assertEqual(INJECTION_SCRIPT.count('<svg viewBox="0 0 44 48"'), 6)
        skins = block("const MASCOT_SKINS = {", "function mascotSvg")
        for skin in ("cat", "candy", "corgi", "mint", "frost", "tea"):
            self.assertIn(f"{skin}:", skins)

    def test_docking_is_limited_to_the_side_walls(self):
        # The companion art is a figure peeking in from a vertical edge, so the
        # top and bottom walls must not offer a dock target any more.
        candidate = block("function dockCandidate", "function applyDockPosition")
        self.assertIn("['left'", candidate)
        self.assertIn("['right'", candidate)
        self.assertNotIn("['top'", candidate)
        self.assertNotIn("['bottom'", candidate)

    def test_skin_picker_lays_out_every_skin(self):
        # A hardcoded five-column grid left the sixth skin on a row of its own.
        self.assertNotIn("repeat(5,", INJECTION_SCRIPT)
        self.assertIn("grid-template-columns:repeat(auto-fit,minmax(72px,1fr))", INJECTION_SCRIPT)

    def test_docked_card_hugs_its_artwork(self):
        # Every sprite is cropped flush to its own cut edge, so a floor width
        # on the card would only ever show as padding beside the narrower
        # companions -- the cat, a head study at 48px tall, is under half the
        # width of the widest of them.
        self.assertIn('.cti-edge-mascot[data-art="true"] { width:auto; min-width:0;', INJECTION_SCRIPT)

    def test_a_new_runtime_rebuilds_the_companion(self):
        # The companion is otherwise only rebuilt when the skin or the dock
        # changes, so a redrawn bitmap would never reach a window that keeps
        # the same skin selected across a plugin update.
        refresh = block("function applyHud", "if (!body.querySelector")
        self.assertIn("if (runtimeChanged) applyMascotSkin(root);", refresh)

    def test_bitmap_art_precedes_the_vector_mascot(self):
        markup = block("function mascotMarkup", "function skinButtons")
        self.assertIn("mascotArt(id)", markup)
        self.assertIn("mascotSvg(id)", markup)
        # Left-hand docks mirror the artwork so the figure still peeks inwards.
        self.assertIn('[data-art="true"][data-edge="left"] img { transform:scaleX(-1); }', INJECTION_SCRIPT)

    def test_bitmap_art_travels_inside_the_injected_script(self):
        # The renderer cannot read the plugin's assets directory, so the
        # artwork has to be inlined rather than referenced by path.
        self.assertNotIn("__COMPANION_ART__", INJECTION_SCRIPT)
        for skin, uri in COMPANION_ART.items():
            with self.subTest(skin=skin):
                self.assertIn(uri[:80], INJECTION_SCRIPT)

    def test_the_bitmap_companion_floats_free_of_its_plate(self):
        # A baked bitmap already carries its own shading and silhouette, so a
        # plate behind it only shows up as a frame drawn around the character.
        # The vector fallback still needs the card for contrast on a light
        # canvas, so the plate has to be scoped to that branch alone.
        art = block('.cti-edge-mascot[data-art="true"] {', '.cti-edge-mascot[data-art="true"] img')
        self.assertIn("border:0", art)
        self.assertIn("background:none", art)
        self.assertIn("box-shadow:none", art)
        self.assertIn('.cti-edge-mascot:not([data-art="true"]) {', INJECTION_SCRIPT)
        # No plate means no rounded plate corners either.
        self.assertNotIn('.cti-edge-mascot[data-edge="left"] { border-radius', INJECTION_SCRIPT)

    def test_the_whole_panel_is_a_grab_surface(self):
        # Dragging used to require the pointer to land on the title row, so the
        # panel could not be moved by its body.
        handler = block("root.addEventListener('pointerdown',event=>{", "},true);")
        self.assertNotIn(".cti-hud-head", handler)
        self.assertIn("button,input,select,textarea,summary,a,label", handler)
        # A pointerdown on the scrollbar gutter is the scroll container's, not
        # the panel drag's, now that the body is draggable too.
        self.assertIn("isOverScrollbar(root,event)", handler)
        self.assertIn("function isOverScrollbar(node,event)", INJECTION_SCRIPT)

    def test_the_skin_picker_collapses(self):
        picker = block("<details data-skins>", "</details>")
        self.assertIn("cti-skin-group", picker)
        self.assertIn("data-skin-current", picker)
        self.assertIn("SKINS_OPEN_KEY = 'cti-skins-open';", INJECTION_SCRIPT)
        self.assertIn("localStorage.getItem(SKINS_OPEN_KEY) === 'true'", INJECTION_SCRIPT)
        self.assertIn("localStorage.setItem(SKINS_OPEN_KEY, String(skins.open));", INJECTION_SCRIPT)
        # The collapsed summary is the only place the live companion is named.
        self.assertIn("querySelector('[data-skin-current]')", INJECTION_SCRIPT)

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
