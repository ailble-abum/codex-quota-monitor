// External legacy consumer probe; no renderer source or artwork is vendored.
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { chromium, webkit } = require('playwright');

async function main() {
  const [legacyScripts, artifacts, mode] = process.argv.slice(2);
  const bridge = mode === '--bridge' ? fs.readFileSync(path.join(__dirname, '../quota_monitor/page_bridge.js'), 'utf8') : null;
  assert.ok(legacyScripts && artifacts, 'Usage: node tools/verify_panel.cjs LEGACY_SCRIPTS ARTIFACT_DIR');
  fs.mkdirSync(artifacts, { recursive: true });
  const fixture = JSON.parse(execFileSync(process.env.PYTHON || 'python3',
    [path.join(__dirname, 'panel_fixture.py'), legacyScripts], { encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 }));
  for (const engine of [chromium, webkit]) {
    const browser = await engine.launch();
    try {
      for (const colorScheme of ['light', 'dark']) {
        const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, colorScheme, locale: 'zh-CN' });
        try {
          const unexpected = [];
          await context.route('**/*', route => {
            if (route.request().url() !== 'http://panel.invalid/') {
              unexpected.push(route.request().url());
              return route.abort();
            }
            return route.fulfill({ contentType: 'text/html; charset=utf-8', body: `<!doctype html><html lang="zh-CN"><meta charset="utf-8">
              <style>:root{color-scheme:light dark}body{background:Canvas;color:CanvasText;font:16px system-ui;padding:32px}button{margin:8px}</style>
              <h1>V2 数据 → 现有面板</h1><p>合成会话 · 离线兼容性验证 · 非现用安装</p>
              <button data-app-action-sidebar-thread-row data-app-action-sidebar-thread-kind="local" data-app-action-sidebar-thread-host-id="local" data-app-action-sidebar-thread-id="one" data-app-action-sidebar-thread-active="true">任务一</button>
              <button data-app-action-sidebar-thread-row data-app-action-sidebar-thread-kind="local" data-app-action-sidebar-thread-host-id="local" data-app-action-sidebar-thread-id="two" data-app-action-sidebar-thread-active="false">任务二</button>
              <button data-app-action-sidebar-thread-row data-app-action-sidebar-thread-kind="local" data-app-action-sidebar-thread-host-id="local" data-app-action-sidebar-thread-id="missing" data-app-action-sidebar-thread-active="false">无记录任务</button>
              </html>` });
          });
          const page = await context.newPage();
          const errors = [];
          page.on('pageerror', error => errors.push(error.message));
          await page.goto('http://panel.invalid/');
          await page.evaluate(() => {
            localStorage.setItem('cti-language', 'zh');
            localStorage.setItem('cti-layout-v2', JSON.stringify({ expanded: { edge: 'right', y: 120 } }));
          });
          const push = key => page.evaluate(({payload, bridge}) => {
            if (!bridge) return window.__codexContextTokenInspectorUpdate(payload);
            return (0, eval)(bridge)({action: 'publish', expected: location.href,
              key: payload.activeThreadId, payload, panel: true, host: 'codex-sidebar'});
          }, {payload: fixture.payloads[key], bridge});
          const select = key => page.evaluate(key => {
            document.querySelectorAll('[data-app-action-sidebar-thread-row]').forEach(row => {
              row.setAttribute('data-app-action-sidebar-thread-active', String(row.getAttribute('data-app-action-sidebar-thread-id') === key));
            });
          }, key);
          const meter = expected => page.waitForFunction(expected => {
            return document.querySelector('[data-context] [role="meter"]')?.getAttribute('aria-valuenow') === String(expected);
          }, expected);
          const empty = () => page.waitForFunction(() => {
            return !document.querySelector('[data-context] [role="meter"]') && document.querySelector('[data-metrics]')?.textContent === '';
          });
          await page.evaluate(({ script, payload }) => (0, eval)(script)(payload), { script: fixture.script, payload: fixture.payloads.one });
          await select('one');
          await push('one');
          await meter(25);
          await page.locator('.cti-edge-mascot').focus();
          await page.locator('[data-details] summary').click();
          assert.match(await page.locator('[data-metrics]').innerText(), /700/);
          await push('one');
          assert.equal(await page.locator('.cti-hud').count(), 1);
          assert.equal(await page.locator('.cti-edge-mascot').count(), 1);
          // Switch host identity before new data arrives: previous task must disappear.
          await page.waitForTimeout(20);
          await select('two');
          await empty();
          await push('two');
          await meter(50);
          assert.match(await page.locator('[data-metrics]').innerText(), /900/);
          await page.locator('.cti-edge-mascot img').evaluate(img => img.decode());
          await page.locator('.cti-edge-mascot').focus();
          await page.screenshot({ path: path.join(artifacts, `${engine.name()}-${colorScheme}.png`) });
          await select('missing');
          await push('missing');
          await empty();
          await select('one');
          await push('one');
          await meter(25);
          // Advance only browser time; replay the unchanged payload to exercise expiry.
          if (bridge) {
            await page.evaluate(() => { performance.now = () => 1e15; });
          } else {
            await page.evaluate(() => { const now = Date.now; Date.now = () => now() + 121000; });
            await push('one');
          }
          await empty();
          assert.deepEqual(errors, []);
          assert.deepEqual(unexpected, []);
          console.log(`${engine.name()} ${colorScheme}: values, switch, missing, expiry, singleton passed`);
        } finally { await context.close(); }
      }
    } finally { await browser.close(); }
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
