import json
import tempfile
import unittest
from pathlib import Path

from companion_art import COMPANION_ART
from context_token_inspector import summarize_session, summarize_session_fast
from context_token_injector import BUILD_STAMP, INJECTION_SCRIPT, RUNTIME_VERSION, build_payload, push, runtime_state


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

    def test_the_quota_header_stays_pinned(self):
        # The panel is its own scroll container, so an unpinned title row takes
        # the quota readout and the window controls off screen with it.
        head = block(".cti-hud-head {", "[data-cti-title]")
        self.assertIn("position: sticky", head)
        self.assertIn("top: 0", head)
        self.assertIn("background: Canvas", head)

    def test_the_companion_gauge_maps_one_cell_per_quota_window(self):
        # An account can be constrained by more than one window at a time, and
        # every one of them needs headroom. One bar could not say that, so the
        # cell count follows what the account reports rather than a plan name
        # the plugin would have to hardcode.
        gauge = block("function applyMascotGauge", "function undockHud")
        self.assertIn("quota.windows", INJECTION_SCRIPT)
        self.assertIn("const readings=windows.length?windows:[null];", gauge)
        self.assertIn("gauge.dataset.cells=String(readings.length);", gauge)
        self.assertIn("gauge.dataset.state=windows.length?'live':'empty';", gauge)

    def test_the_gauge_never_shows_a_full_bar_it_cannot_vouch_for(self):
        # A full default would report a healthy account while the plugin knows
        # nothing, which is how the old decorative pill behaved.
        self.assertIn('[data-state="empty"] .cti-gauge-cell', INJECTION_SCRIPT)
        self.assertIn("border:1px dashed", INJECTION_SCRIPT)
        self.assertIn("'<span class=\"cti-gauge-cell\"></span>'", INJECTION_SCRIPT)

    def test_a_reached_limit_is_shown_on_the_gauge(self):
        # Reaching one window stops the account even while the other still has
        # headroom, so it is flagged separately from the fills.
        gauge = block("function gaugeReading", "function applyMascotGauge")
        self.assertIn("quota.ordinaryUsageAllowed===false", gauge)
        self.assertIn("quota.rateLimitReachedType", gauge)
        self.assertIn("blocked:live&&", gauge)
        self.assertIn('data-blocked="true"', INJECTION_SCRIPT)
        self.assertIn("gauge.dataset.blocked=String(blocked);", INJECTION_SCRIPT)

    def test_a_blocked_account_cannot_render_as_partly_usable(self):
        # Reaching one window stops the account while the other still shows
        # headroom, and filling each cell with its own share drew exactly that
        # case as "partly usable". Under a block the cells carry no fills at
        # all, and the bar across them states the block instead of the shares.
        start = INJECTION_SCRIPT.index("if(blocked)return")
        blocked_branch = INJECTION_SCRIPT[start:INJECTION_SCRIPT.index("\n", start)]
        self.assertNotIn("<i ", blocked_branch)
        self.assertIn("gaugeColor('low')", blocked_branch)
        self.assertIn('[data-gauge][data-blocked="true"]::after', INJECTION_SCRIPT)

    def test_the_gauge_names_the_reset_it_is_waiting_for(self):
        # The countdown is the actionable half of a block, and the accessible
        # name is the only channel with room for it.
        gauge = block("function applyMascotGauge", "function undockHud")
        self.assertIn("nearestResetText(windows)", gauge)

    def test_a_block_is_stated_once(self):
        # The headline reports a block whenever there is a window to report it
        # against, so the footnote only has to cover an account that reached a
        # limit without reporting any window.
        self.assertIn("!quota.windows.length && (quota.ordinaryUsageAllowed === false", INJECTION_SCRIPT)
        self.assertIn("if (notes.length) quotaHtml", INJECTION_SCRIPT)

    def test_the_collapsed_bar_answers_with_a_duration(self):
        # The meter already draws each window's share, so the figure beside it
        # is spent on the question the panel exists for: whether what is ahead
        # fits. A block overrides it, because that is an availability question
        # rather than a magnitude one.
        title = block("function updateHudTitle", "function clearFooters")
        self.assertIn("windowBudgetText(w)", title)
        self.assertIn("accountBudgetText(q)", title)
        self.assertIn("'已停'", title)
        # Trading the percentages for durations must not lose them, and the
        # collapsed title's own text already is the compact reading, so naming
        # both would say every window twice.
        self.assertIn("title.setAttribute('aria-label',[compact,budget,", title)

    def test_a_window_that_refills_first_reports_a_floor(self):
        # A window that will not run out before it refills cannot bind, so its
        # honest figure is a floor. Without the sign a comfortable account gets
        # a number that reads like a deadline.
        text = block("function windowBudgetText", "function accountBudgetText")
        self.assertIn("`≥${shortDuration(resetIn)}`", text)
        self.assertIn("shortDuration(exhaust)", text)

    def test_the_panel_reports_the_build_it_is_running(self):
        # The declared version, the cachebuster Codex keys its cache directory
        # on, and the runtime version all move independently, and a plugin cache
        # does not refresh on its own.
        settings = block("<div data-settings hidden>", "data-freshness")
        self.assertIn("data-build", settings)
        self.assertIn("payload.build", INJECTION_SCRIPT)
        self.assertIn("put('[data-build]'", INJECTION_SCRIPT)

    def test_the_reported_runtime_version_is_the_one_being_pushed(self):
        # Read back out of the script rather than restated beside it, so the
        # number the panel shows cannot drift from what the overlay runs.
        self.assertIsInstance(RUNTIME_VERSION, int)
        self.assertIn(f"const RUNTIME_VERSION = {RUNTIME_VERSION};", INJECTION_SCRIPT)
        self.assertEqual(BUILD_STAMP['runtimeVersion'], RUNTIME_VERSION)

    def test_the_panel_probes_the_selectors_it_depends_on(self):
        # A Codex update can drift the selectors the overlay uses to find the
        # active thread; reporting which landed keeps that from silently
        # drawing a smaller panel.
        settings = block("<div data-settings hidden>", "data-freshness")
        self.assertIn("data-dom", settings)
        self.assertIn("payload.dom", INJECTION_SCRIPT)
        self.assertIn("put('[data-dom]'", INJECTION_SCRIPT)
        self.assertIn("sidebarRows", INJECTION_SCRIPT)
        self.assertIn("conversationId", INJECTION_SCRIPT)
        # A thread list with no marked-active row, or none at all, is named as
        # drift rather than left to the user to infer.
        self.assertIn("UI may have changed", INJECTION_SCRIPT)
        self.assertIn("界面可能已更新", INJECTION_SCRIPT)
        # The probe also travels back into the injector's own log line.
        self.assertIn("dom: payload.dom", INJECTION_SCRIPT)

    def test_runtime_state_collects_the_dom_probe(self):
        class FakeClient:
            def evaluate(self, expression):
                self.expression = expression
                return {
                    'href': 'https://x', 'title': 'y', 'activeThreadId': None,
                    'dom': {'sidebarRows': 3, 'activeRow': True, 'conversationId': True},
                }

        client = FakeClient()
        state = runtime_state(client)
        self.assertEqual(
            state['dom'],
            {'sidebarRows': 3, 'activeRow': True, 'conversationId': True},
        )
        # The probe is read from the live page, not synthesized from the payload.
        self.assertIn("document.querySelectorAll('[data-app-action-sidebar-thread-row]')", client.expression)

    def test_the_settings_footer_names_the_privacy_promise(self):
        # The strongest differentiator lives in the README today; the panel is
        # where a user who never reads docs still gets told, in one line, that
        # nothing leaves the machine.
        settings = block("<div data-settings hidden>", "data-freshness")
        self.assertIn("只读 · 本机 · 不上传", settings)
        self.assertIn("Read-only · local · never uploaded", settings)

    def test_the_script_leaves_a_data_only_update_handle(self):
        # A resident renderer already carrying this runtime must not have the
        # whole script, companion bitmaps and all, re-parsed every ten seconds.
        tail = block("window.__codexContextTokenInspectorUpdate =", "return {")
        self.assertIn("installObserver(nextPayload)", tail)
        self.assertIn("applyAll(nextPayload)", tail)

    def test_push_skips_the_script_when_the_runtime_is_applied(self):
        class Recorder:
            def __init__(self, applied):
                self._applied = applied
                self.expressions = []

            def evaluate(self, expression):
                self.expressions.append(expression)
                if len(self.expressions) == 1:
                    return self._applied
                return {'ok': True}

        applied = Recorder(True)
        self.assertEqual(push(applied, {'quota': {}}), {'ok': True})
        self.assertEqual(len(applied.expressions), 2)
        # First the probe, then a data-only call -- never the full script.
        self.assertIn('__codexContextTokenInspectorRuntimeVersion === ', applied.expressions[0])
        self.assertIn('__codexContextTokenInspectorUpdate(', applied.expressions[1])
        self.assertNotIn('RUNTIME_VERSION = ', applied.expressions[1])

        stale = Recorder(False)
        push(stale, {'quota': {}})
        self.assertEqual(len(stale.expressions), 2)
        # A replaced renderer has no version handle, so the full script lands.
        self.assertIn('RUNTIME_VERSION = ', stale.expressions[1])

    def test_the_gauge_follows_quota_and_not_only_the_skin(self):
        # The companion is rebuilt only when the skin or the dock changes, so a
        # gauge reached through that path alone would freeze at the reading
        # taken when the skin last changed.
        refresh = block("function applyHud", "if (!body.querySelector")
        self.assertIn("applyMascotGauge(root);", refresh)
        # Replacing the markup on a skin change drops the gauge with it.
        self.assertIn("applyMascotGauge(root);", block("function applyMascotSkin", "function gaugeColor"))

    def test_the_gauge_stays_inside_the_companion_hit_area(self):
        # It is drawn outside the artwork's box for a bitmap companion, and a
        # pointer-events opt-out there would turn a sweep from the character
        # onto the gauge into a pointerleave, hiding the panel.
        gauge = block('.cti-edge-mascot [data-gauge] {', '.cti-edge-mascot [data-gauge] .cti-gauge-cell')
        self.assertNotIn("pointer-events", gauge)

    def test_the_bitmap_caption_is_not_written_back_on_every_pass(self):
        # The accessible name is composed from a base kept on the element;
        # reading it back from the element would append to it each pass.
        skin = block("function applyMascotSkin", "function gaugeColor")
        self.assertIn("mascot.dataset.skinLabel=", skin)
        self.assertNotIn("mascot.getAttribute('aria-label')", skin)

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
