"""Build an attributed, isolated candidate from one frozen external renderer.

Not a general JS rewriter, installer, or claim of independent renderer authorship.
Only the newly written adapter is stored in V2; retained source stays external.
"""
import argparse
import ast
import hashlib
import json
import re
from pathlib import Path

BASE = '2705f32a6f080ee1bdbecdc5b43f5fe0f9045eed'
HASHES = {
    'context_token_injector.py': '2b308296d1b928e39d847cd1de477ebc4587191aa6b5813838d7fdc9074d1b57',
    'companion_feedback.py': 'e954ed4ce8f4e026779a61ebeba4b5b87774ab6073cd3e6355f744e62c0a80fa',
    'companion_art.py': 'bf82328005097b4af6df60b5c158f5f15230e0378b2cad06693ced15a5bb1865',
    'companion_expressions.py': '1be738c3a9d7a1965df6cff09c3929ee12a5550b1fb88c893da165888e13138a',
    'LICENSE': '3173384c5ec386cd808211ded2d3634f2521f9a92de981d2a104a2b42b291b40',
    'NOTICE': '5e524e54bbf3d1839d6e695e5adc189e459921e619612e153d9da703c1729267',
}


def literal(source, name):
    for node in ast.parse(source).body:
        targets = node.targets if isinstance(node, ast.Assign) else (
            [node.target] if isinstance(node, ast.AnnAssign) else [])
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            return ast.literal_eval(node.value)
    raise ValueError('constant missing')


def cut(source, start, end):
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError('unexpected source boundary')
    a, b = source.index(start), source.index(end)
    if b <= a:
        raise ValueError('reversed source boundary')
    return source[:a] + source[b:]


def panel_css(template):
    """Bounded cleanup for the hash-pinned template, not a general CSS parser."""
    start, end = '      .cti-hud {\n', '      .cti-reply-footer {'
    if template.count(start) != 1 or template.count(end) != 1:
        raise ValueError('unexpected CSS boundary')
    if template.index(start) >= template.index(end):
        raise ValueError('reversed CSS boundary')
    css = template[template.index(start):template.index(end)]
    # Only bare attribute selectors at a line/comma boundary; :where keeps
    # existing specificity, including the title pseudo-element rule.
    css, count = re.subn(r'(^[ \t]*|,[ \t]*)(\[data-[^\]]+\])',
                        r'\1:where(#codex-context-token-inspector-root) \2',
                        css, flags=re.MULTILINE)
    if count != 13:
        raise ValueError('unexpected CSS selector count')
    return '`' + css + '`'


def build(directory):
    texts = {}
    for name, digest in HASHES.items():
        with (Path(directory) / name).open('rb') as stream:
            data = stream.read(1048577)
        if len(data) > 1048576 or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('unrecognized source revision')
        texts[name] = data.decode('utf-8')
    script = literal(texts['context_token_injector.py'], 'INJECTION_SCRIPT')
    # Retained view helpers run behind V2 ownership/lifetime checks.
    script = script.replace('function ensureMascot(root)', 'function createRetainedMascot(root)', 1)
    script = script.replace('function positionContextHint(', 'function positionRetainedHint(', 1)
    script = cut(script, '  const previousRuntimeVersion', '  const I18N')
    script = script.replace('  const I18N', '  const runtimeChanged = true;\n  const I18N', 1)
    # Extract only retained visual templates; replace their mounting functions.
    def template(function, declaration):
        section = script.split('  function ' + function + '(', 1)[1]
        value = section.split(declaration + ' = `', 1)[1].split('`;', 1)[0]
        return '`' + value + '`'
    visual = ('  const panelCSS = () => ' + panel_css(template('ensureStyle', 'const css')) + ';\n'
              + '  const panelBodyTemplate = zh => ' + template('applyHud', 'body.innerHTML') + ';\n')
    # V2 has no quota notification producer or sender. Keep the legacy preference untouched.
    for old, new in (
            ('<input type="checkbox" data-alerts>', '<input type="checkbox" data-alerts disabled aria-describedby="cti-quota-alerts-unavailable">'),
            ('''<div class="cti-muted">${zh?'每个配额窗口仅提醒一次。系统需允许通知。':'Once per quota window. System notifications must be allowed.'}</div>''',
             '''<div class="cti-muted" id="cti-quota-alerts-unavailable">${zh?'配额通知尚未接通。':'Quota notifications are not connected yet.'}</div>''')):
        if visual.count(old) != 1:
            raise ValueError('unexpected quota notification template')
        visual = visual.replace(old, new)
    # Exact source digests make these bounded spans safe; unknown revisions stop.
    for start, end in (
            ('  function n(', '  function quotaTone('),
            ('  function summaryHover(', '  function ensureStyle('),
            ('  function ensureStyle(', '  function cleanOriginalTitle('),
            ('  function ensureHud(', '  function applySidebar('),
            ('  function cleanOriginalTitle(', '  function hudMode('),
            ('  function applySidebar(', '  function applyHud(')):
        script = cut(script, start, end)
    script = cut(script, "    if (!body.querySelector('[data-quota]')", "      const language=body.querySelector('[data-language]');")
    script = script.replace("      const language=body.querySelector('[data-language]');",
                            "    if (preparePanelBody(root)) {\n      const language=body.querySelector('[data-language]');", 1)
    script = cut(script, '  function uiLanguage(', '  function tr(')
    script = cut(script, '  function tr(', '  // Bitmap companions')
    script = cut(script, "      const language=body.querySelector('[data-language]');", "      body.querySelectorAll('[data-layout-preset]')")
    script = cut(script, "      body.querySelector('[data-handoff]').addEventListener(", "      alerts.checked = localStorage.getItem('cti-alerts')")
    script = cut(script, "      const details = body.querySelector('[data-details]');", "      const alerts = body.querySelector('[data-alerts]');")
    script = cut(script, "      for(const setting of ['motion','reminders'])", "      const alerts = body.querySelector('[data-alerts]');")
    for old, new, expected in (
            ("localStorage.getItem('cti-companion-motion')!=='false'", "companionPreference('motion')", 2),
            ("localStorage.getItem('cti-companion-motion')==='false'", "!companionPreference('motion')", 1),
            ("localStorage.getItem('cti-context-reminders')==='false'", "!companionPreference('context')", 1),
            ("localStorage.getItem('cti-companion-reminders')==='false'", "!companionPreference('reminders')", 1)):
        if script.count(old) != expected:
            raise ValueError('unexpected companion preference readers')
        script = script.replace(old, new)
    script = cut(script, "      const alerts = body.querySelector('[data-alerts]');", "      body.querySelector('[data-position-reset]').addEventListener(")
    script = cut(script, '  function layoutPreset(', '  function presetWidth(')
    script = cut(script, '  function updatePresetButtons(', '  function setLayoutPreset(')
    script = cut(script, "      body.querySelectorAll('[data-layout-preset]')", "      body.querySelector('[data-mascot-scale]').addEventListener(")
    script = cut(script, '  function saveLayout(', '  function dockSafeTop(')
    old_write = '    localStorage.setItem(LAYOUT_PRESET_KEY,preset);'
    if script.count(old_write) != 1:
        raise ValueError('unexpected layout preset writer')
    script = script.replace(old_write, '    setLayoutPreference(preset);')
    script = cut(script, '  function mascotScale()', '  function edgeDockEnabled(')
    script = cut(script, "      body.querySelector('[data-mascot-scale]').addEventListener(", '      updateMascotSizeControls(root);')
    script = cut(script, '  function edgeDockEnabled(', '  function mascotArt(')
    script = cut(script, "      const edgeDock=body.querySelector('[data-edge-dock]');", "      body.querySelectorAll('[data-skin-choice]')")
    script = cut(script, '  function mascotSkin(', '  // Logical window dimensions')
    script = cut(script, '  function updateSkinButtons(', '  function quotaTone(')
    script = cut(script, "      body.querySelectorAll('[data-skin-choice]')", '      updateSkinButtons(root);')
    script = cut(script, '  function readLayout(', '  function hudBase(')
    script = cut(script, '      root.__ctiLayout=readLayout();', '    const mode=hudMode(root), layout=root.__ctiLayout;')
    script = script.replace('    const mode=hudMode(root), layout=root.__ctiLayout;',
                            '      root.__ctiLayout=initialPanelLayout();\n    }\n    const mode=hudMode(root), layout=root.__ctiLayout;', 1)
    # Remove these after the intervening old mount/sidebar spans are gone.
    script = cut(script, '  function updateUnitButtons(', '  function applyHud(')
    start, end = '    if (selected) {', '    const errorLabels='
    if script.count(start) != 1 or script.count(end) != 1:
        raise ValueError('unexpected session detail boundary')
    a, b = script.index(start), script.index(end)
    if b <= a:
        raise ValueError('reversed session body boundary')
    script = (script[:a] + '    renderSessionDetails(body, selected);\n'
              + '    renderContext(body, selected);\n' + script[b:])
    script = cut(script, "    body.querySelector('[data-health]').setAttribute(",
                 '    renderSessionDetails(body, selected);')
    script = script.replace('    renderSessionDetails(body, selected);',
                            '    renderHealth(body, health);\n    renderSessionDetails(body, selected);', 1)
    script = cut(script, '    const errorLabels=', '    const stamp = payload.build')
    script = script.replace('    const stamp = payload.build',
                            '    renderAccountStatus(body, quota, live, age);\n    const stamp = payload.build', 1)
    script = script.replace("payload.quota || {status:'loading', windows:[]}",
                            "payload.quota || {status:'unavailable', windows:[]}", 1)
    script = cut(script, '    const age=quota.updatedAt?', '    const windows=live&&')
    script = script.replace('    const windows=live&&',
                            '    const {live} = accountFreshness(quota);\n    const windows=live&&', 1)
    script = cut(script, '    const age = quota.updatedAt ?', '    const stoppedAccount =')
    script = script.replace('    const stoppedAccount =',
                            '    const {age, live} = accountFreshness(quota);\n    const stoppedAccount =', 1)
    script = cut(script, "    const live = q?.status === 'live'", '    const windows = live ?')
    script = script.replace('    const windows = live ?',
                            '    const {live} = accountFreshness(q);\n    const windows = live ?', 1)
    script = cut(script, "    let quotaHtml = '';", '    const id = activeThreadId();')
    script = script.replace('    const id = activeThreadId();',
                            '    renderAccountOverview(body, quota, live, stoppedAccount);\n    const id = activeThreadId();', 1)
    script = cut(script, '  function accountBudgetText(', '  function nearestResetText(')
    script = cut(script, '  function windowBudgetText(', '  function nearestResetText(')
    script = cut(script, '  function shortDuration(', '  function pressure(')
    script = cut(script, '  function clearDockHide(', '  function scheduleDockHide(')
    script = cut(script, '  function scheduleDockHide(', '  function revealDock(')
    script = cut(script, '  function revealDock(', '  function dockVerticalY(')
    script = cut(script, '  function undockHud(', '  function dockCandidate(')
    script = cut(script, '  function applyDockPosition(', '  function applyStoredHudPosition(')
    script = cut(script, '  function applyStoredHudPosition(', '  function presetWidth(')
    script = cut(script, '  function syncExpandedAnchor(', '  function setLayoutPreset(')
    script = cut(script, '  function setLayoutPreset(', '  function resizeGeometry(')
    script = cut(script, '  function installHudDrag(', '  function keepTogglePosition(')
    script = cut(script, '  function keepTogglePosition(', '  function applyHud(')
    script = cut(script, '  function clampHud(', '  function contextHintGeometry(')
    script = cut(script, '  function quotaTone(', '  function hudMode(')
    script = cut(script, '  function hudMode(', '  function dockSafeTop(')
    script = cut(script, '  function dockSafeTop(', '  function dockVerticalY(')
    script = cut(script, '  function dockVerticalY(', '  __COMPANION_FEEDBACK__')
    script = cut(script, '  function dockCandidate(', '  function presetWidth(')
    script = cut(script, '  function presetWidth(', '  function resizeGeometry(')
    script = cut(script, '  function resizeGeometry(', '  function applyHud(')
    script = cut(script, '  function gaugeColor(', '  function applyMascotGauge(')
    script = cut(script, '  function contextHintGeometry(', '  function positionRetainedHint(')
    script = cut(script, '    const stamp = payload.build', '    updateHudTitle(root);\n    updateUnitButtons(root);')
    script = script.replace('    updateHudTitle(root);\n    updateUnitButtons(root);',
                            '    renderDiagnostics(body, payload);\n    updateHudTitle(root);\n    updateUnitButtons(root);', 1)
    script = cut(script, '    const put = (selector, html) => {', '    const quota = payload.quota')
    script = cut(script, "      body.querySelector('[data-position-reset]').addEventListener(", "    const quota = payload.quota")
    script = script.replace("    const quota = payload.quota", "    }\n    const quota = payload.quota", 1)
    tail = '  function clearFooters('
    if script.count(tail) != 1:
        raise ValueError('unexpected lifecycle boundary')
    assets = Path(__file__).parents[1] / 'quota_monitor'
    script = (script[:script.index(tail)] + (assets / 'panel_format.js').read_text()
              + (assets / 'panel_time.js').read_text()
              + (assets / 'panel_metrics.js').read_text()
              + (assets / 'panel_geometry.js').read_text()
              + (assets / 'panel_layout_runtime.js').read_text()
              + (assets / 'panel_templates.js').read_text()
              + (assets / 'panel_language.js').read_text()
              + (assets / 'panel_companion_preferences.js').read_text()
              + (assets / 'panel_layout_data.js').read_text()
              + (assets / 'panel_layout_preference.js').read_text()
              + (assets / 'panel_scale_preference.js').read_text()
              + (assets / 'panel_edge_preference.js').read_text()
              + (assets / 'panel_skin_preference.js').read_text()
              + (assets / 'panel_controls.js').read_text()
              + (assets / 'panel_details.js').read_text()
              + (assets / 'panel_context.js').read_text()
              + (assets / 'panel_health.js').read_text()
              + (assets / 'panel_account_status.js').read_text()
              + (assets / 'panel_account_windows.js').read_text()
              + (assets / 'panel_account_overview.js').read_text()
              + (assets / 'panel_diagnostics.js').read_text() + visual
              + (assets / 'panel_disclosures.js').read_text()
              + (assets / 'panel_body.js').read_text()
              + (assets / 'panel_handoff.js').read_text()
              + (assets / 'panel_position_reset.js').read_text()
              + (assets / 'panel_mount.js').read_text()
              + (assets / 'panel_adapter.js').read_text())
    guard = """(payload => {
  if (document.getElementById('codex-context-token-inspector-root') ||
      document.getElementById('codex-context-token-inspector-style') ||
      document.getElementById('codex-context-token-inspector-mascot'))
    throw new Error('consumer DOM occupied');"""
    script = script.replace('(payload => {', guard, 1)
    for marker, filename, name in (
            ('__COMPANION_FEEDBACK__', 'companion_feedback.py', 'COMPANION_FEEDBACK_JS'),
            ('__COMPANION_ART__', 'companion_art.py', 'COMPANION_ART'),
            ('__COMPANION_EXPRESSIONS__', 'companion_expressions.py', 'COMPANION_EXPRESSIONS')):
        value = literal(texts[filename], name)
        script = script.replace(marker, value if isinstance(value, str) else json.dumps(value))
    header = ('// Isolated derived candidate; retained renderer from ' + BASE + '.\n'
              '// Copyright (c) 2026 Kevin Ke; Copyright (c) 2026 Ailble.\n'
              '// MIT: accompanying LICENSE and NOTICE must travel with this file.\n')
    return header + script, texts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_dir', type=Path, help='Four frozen scripts plus original LICENSE/NOTICE')
    parser.add_argument('output_dir', type=Path, help='New directory; never overwrites an existing bundle')
    args = parser.parse_args()
    script, texts = build(args.source_dir)
    args.output_dir.mkdir()  # Existing output must be explicitly retained or removed by its owner.
    (args.output_dir / 'consumer.js').write_text(script, encoding='utf-8')
    for name in ('LICENSE', 'NOTICE'):
        (args.output_dir / name).write_text(texts[name], encoding='utf-8')
    manifest = {'sourceCommit': BASE, 'sourceSHA256': HASHES,
                'consumer': {'path': 'consumer.js', 'sha256': hashlib.sha256(script.encode()).hexdigest()},
                'status': 'derived-isolated-candidate',
                'changes': 'Removed host/sidebar/message scans and observer lifecycle; V2 snapshot-only adapter, owned DOM lifecycle, pruned and attribute-scoped retained CSS, V2 finite-number formatting and control state/language projection with lazy unit preferences; text-only session detail, context meter and validated health projection; text-only account status with unavailable default and shared freshness checks.'}
    (args.output_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest['consumer']))


if __name__ == '__main__':
    main()
