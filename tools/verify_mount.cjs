// Owned mounts and delegated controls against a generated, attributed candidate.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium, webkit} = require('playwright');
(async () => {
  const script = fs.readFileSync(process.argv[2], 'utf8');
  const bridge = fs.readFileSync(path.join(__dirname, '../quota_monitor/page_bridge.js'), 'utf8');
  for (const engine of [chromium, webkit]) {
    const browser = await engine.launch();
    try {
      const page = await browser.newPage();
      await page.route('**/*', route => route.fulfill({body: '<html><head></head><body></body></html>', contentType: 'text/html'}));
      await page.goto('http://mount.invalid/');
      await page.evaluate(() => { window.__quotaMonitorV2Thread = 'one'; localStorage.setItem('cti-language', 'zh'); });
      const call = options => page.evaluate(({bridge, options}) => (0, eval)(bridge)(options), {bridge, options});
      const base = {expected: 'http://mount.invalid/', key: 'one'};
      // Host attributes are deliberately identical to retained panel attributes.
      const hostStyle = () => page.evaluate(() => [...document.querySelectorAll('#host-probe *')].map(node => {
        const style = getComputedStyle(node);
        return [style.display, style.fontSize, style.padding, style.margin, style.color, style.cursor,
          getComputedStyle(node, '::before').content];
      }));
      await page.evaluate(() => {
        const host = document.createElement('article'); host.id = 'host-probe';
        host.innerHTML = '<span data-cti-title>Host</span><span data-update>Update</span>' +
          '<div data-context>Context</div><div data-health data-warning="true">Health</div>' +
          '<div data-explanation>Explanation</div><span data-mascot-scale-value>Scale</span>' +
          '<details data-details open><summary>Details</summary><div>Body</div></details>' +
          '<details data-skins open><summary>Skin<em>Label</em></summary><div>Body</div></details>';
        document.body.append(host);
      });
      const before = await hostStyle();
      assert.equal(await call({...base, action: 'initialize', consumer: {source: script}}), 'ready');
      assert.deepEqual(await hostStyle(), before, 'panel CSS must not style host attributes');
      await page.locator('#host-probe').evaluate(node => node.remove());
      const payload = {activeThreadId: 'one', selectedThreadId: 'one', observedAt: Date.now()/1000,
        summaries: [{thread_id: 'one', latest_context_tokens: 500, context_window: 1000, latest_context_percent: 50}], detailsByThread: {}};
      const publish = () => call({...base, action: 'publish', payload, panel: true});
      for (let i = 0; i < 4; i++) assert.equal(await publish(), true);
      assert.equal(await page.locator('[data-refresh]').isDisabled(), true);
      assert.equal(await page.locator('.cti-hud').count(), 1);
      for (const [language, htmlLang, autoLabel, rawLabel, groupLabel] of [
        ['en', 'en', 'Auto', 'raw', 'Token unit'], ['zh', 'zh-CN', '自动', '原值', 'Token 单位']
      ]) {
        await page.evaluate(language => localStorage.setItem('cti-language', language), language);
        await publish();
        assert.equal(await page.locator('.cti-hud').getAttribute('lang'), htmlLang);
        assert.equal(await page.locator('[data-cti-unit="auto"]').textContent(), autoLabel);
        assert.equal(await page.locator('[data-cti-unit="raw"]').textContent(), rawLabel);
        assert.equal(await page.locator('.cti-unit-group').getAttribute('aria-label'), groupLabel);
      }

      const toggle = page.locator('[data-cti-toggle]');
      await toggle.click();
      assert.equal(await page.locator('.cti-hud').getAttribute('data-collapsed'), 'true');
      assert.equal(await toggle.getAttribute('aria-label'), '展开监控');
      await page.locator('[data-cti-title]').focus();
      await page.keyboard.press('Enter');
      assert.equal(await page.locator('.cti-hud').getAttribute('data-collapsed'), 'false');
      assert.equal(await toggle.getAttribute('aria-label'), '收起监控');
      await page.locator('[data-settings-toggle]').click();
      assert.equal(await page.locator('[data-settings-toggle]').getAttribute('aria-expanded'), 'true');
      await page.locator('[data-cti-unit="raw"]').click();
      assert.equal(await page.evaluate(() => localStorage.getItem('codex-context-token-inspector-unit')), 'raw');
      assert.equal(await page.locator('[data-context] [role="meter"]').getAttribute('aria-valuenow'), '50');
      for (const [unit, expected] of [['k', '0.50K / 1.00K'], ['m', '0.00M / 0.00M'], ['auto', '500 / 1K'], ['raw', '500 / 1,000']]) {
        await page.locator(`[data-cti-unit="${unit}"]`).click();
        assert.ok((await page.locator('[data-context]').textContent()).includes(expected), unit);
        assert.deepEqual(await page.locator('[data-cti-unit]').evaluateAll(buttons => buttons.map(button => [button.dataset.ctiUnit, button.dataset.active, button.getAttribute('aria-pressed')])),
          ['auto', 'raw', 'k', 'm'].map(value => [value, String(value === unit), String(value === unit)]));
      }

      await page.locator('[data-settings-toggle]').click();
      assert.equal(await page.locator('[data-settings-toggle]').getAttribute('aria-expanded'), 'false');
      // Drag suppression is an existing layout contract, not a second click.
      await page.evaluate(() => { document.querySelector('.cti-hud').__ctiSuppressToggle = true; });
      await page.locator('[data-cti-toggle]').evaluate(button => button.click());
      assert.equal(await page.locator('.cti-hud').getAttribute('data-collapsed'), 'false');
      await page.evaluate(() => {
        const old = document.querySelector('.cti-hud');
        const other = document.createElement('section');
        other.id = old.id;
        other.textContent = 'Other owner';
        old.replaceWith(other);
      });
      await assert.rejects(publish());
      assert.equal(await page.locator('#codex-context-token-inspector-root').textContent(), 'Other owner');
      console.log(engine.name() + ': one mount, controls, keyboard, unit, suppression, foreign replacement protection passed');
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
