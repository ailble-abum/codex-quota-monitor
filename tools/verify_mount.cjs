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
      await page.evaluate(() => { window.__quotaMonitorV2Thread = 'one'; localStorage.setItem('cti-language', 'zh'); localStorage.setItem('codex-context-token-inspector-unit', 'k'); });
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
      assert.equal(await page.evaluate(() => localStorage.getItem('codex-context-token-inspector-unit')), 'k');
      assert.equal(await page.evaluate(() => localStorage.getItem('codex-context-token-inspector-unit-defaulted')), null);
      const payload = {activeThreadId: 'one', selectedThreadId: 'one', observedAt: Date.now()/1000,
        summaries: [{thread_id: 'one', latest_context_tokens: 500, context_window: 1000, latest_context_percent: 50}], detailsByThread: {}};
      const publish = () => call({...base, action: 'publish', payload, panel: true});
      for (let i = 0; i < 4; i++) assert.equal(await publish(), true);
      Object.assign(payload.summaries[0], {model: '<b data-untrusted-model>model & name</b>',
        reasoning_effort: '<i>high</i>', latest_turn_total_tokens: 550, session_total_tokens: 900,
        latest_turn_input_tokens: 400, latest_turn_cached_input_tokens: 100, latest_turn_output_tokens: 150});
      await publish();
      assert.equal(await page.locator('[data-explanation] b, [data-explanation] i').count(), 0);
      assert.ok((await page.locator('[data-explanation]').textContent()).includes(payload.summaries[0].model));
      assert.ok((await page.locator('[data-explanation]').textContent()).includes('25.0%'));
      assert.equal(await page.locator('[data-metrics] .cti-metric').count(), 2);
      payload.summaries[0].latest_turn_cached_input_tokens = -1;
      await publish();
      assert.ok((await page.locator('[data-explanation]').textContent()).includes('缓存占比: —'));
      for (const [input, cached, expected] of [[0, 0, '—'], [100, 200, '100.0%'], [100, 0, '0.0%'], ['100', 25, '—']]) {
        Object.assign(payload.summaries[0], {latest_turn_input_tokens: input, latest_turn_cached_input_tokens: cached});
        await publish();
        assert.ok((await page.locator('[data-explanation]').textContent()).includes('缓存占比: ' + expected));
      }
      await page.evaluate(() => { window.detailNode = document.querySelector('[data-metrics]').firstChild; });
      await publish();
      assert.equal(await page.evaluate(() => window.detailNode === document.querySelector('[data-metrics]').firstChild), true);
      const summary = payload.summaries.pop();
      await publish();
      assert.equal(await page.locator('[data-metrics]').textContent(), '');
      assert.equal(await page.locator('[data-explanation]').textContent(), '');
      payload.summaries.push(summary);
      await publish();

      payload.healthThreadId = 'one';
      payload.health = {count: 2, after: 500, afterPercent: 50, recommendHandoff: true, reason: 'baseline'};
      await publish();
      assert.equal(await page.locator('[data-health]').getAttribute('data-warning'), 'true');
      assert.ok((await page.locator('[data-health]').textContent()).includes('50.0%'));
      payload.health.count = '<b>2</b>';
      await publish();
      assert.equal(await page.locator('[data-health] b').count(), 0);
      assert.equal(await page.locator('[data-health]').getAttribute('data-warning'), 'false');
      assert.ok((await page.locator('[data-health]').textContent()).includes('暂不可用'));
      payload.healthThreadId = 'other';
      await publish();
      assert.ok((await page.locator('[data-health]').textContent()).includes('尚未观察'));
      delete payload.health; delete payload.healthThreadId;
      await publish();
      await page.evaluate(() => { window.savedNow = Date.now; Date.now = () => 2000000000000; });
      payload.observedAt = 2000000000;
      for (const [timestamp, fresh] of [[2000000000, true], [1999999880, false], [2000000001, false], [undefined, false], ['2000000000', false]]) {
        payload.quota = {status: 'live', updatedAt: timestamp, windows: [{remaining: 80, duration: 300}]};
        await publish();
        assert.equal(await page.locator('[data-quota] [role=meter]').count(), fresh ? 1 : 0);
        assert.equal(await page.locator('.cti-hud').getAttribute('data-tone'), fresh ? 'safe' : 'unknown');
        assert.equal(await page.locator('[data-gauge]').getAttribute('data-state'), fresh ? 'live' : 'empty');
        assert.ok((await page.locator('[data-freshness]').textContent()).includes(fresh ? '刚刚更新' : '账户配额未更新'));
      }
      for (const windows of [null, {}, [null], [{remaining: '80'}], [{remaining: 101}], [{remaining: 80}, {remaining: -1}], [{remaining: 80, resetsAt: 1e20}]]) {
        payload.quota = {status: 'live', updatedAt: 2000000000, windows};
        await publish();
        assert.equal(await page.locator('[data-quota] [role=meter]').count(), 0);
        assert.equal(await page.locator('.cti-hud').getAttribute('data-tone'), 'unknown');
        assert.equal(await page.locator('[data-gauge]').getAttribute('data-state'), 'empty');
        assert.ok((await page.locator('[data-freshness]').textContent()).includes('账户配额未更新'));
        assert.equal(await page.locator('[data-context] [role=meter]').getAttribute('aria-valuenow'), '50');
      }
      payload.quota.windows = [{remaining: 0}, {remaining: 100}];
      await publish();
      assert.equal(await page.locator('[data-quota] [role=meter]').count(), 2);
      assert.equal(await page.locator('[data-gauge]').getAttribute('data-state'), 'live');
      await page.evaluate(() => { window.quotaNode = document.querySelector('.cti-quota-window'); });
      await publish();
      assert.equal(await page.evaluate(() => window.quotaNode === document.querySelector('.cti-quota-window')), true);
      payload.quota.ordinaryUsageAllowed = false;
      await publish();
      assert.deepEqual(await page.locator('.cti-quota-window').evaluateAll(nodes => nodes.map(node => node.dataset.tone)), ['low', 'low']);
      if (process.argv[3]) {
        fs.mkdirSync(process.argv[3], {recursive: true});
        // Inspect card styling separately from the retained auto-docking layout.
        const visual = await browser.newPage({viewport: {width: 600, height: 900}});
        const markup = await page.evaluate(() => ({css: document.getElementById('codex-context-token-inspector-style').textContent,
          quota: document.querySelector('[data-quota]').outerHTML}));
        await visual.setContent(`<style>:root{color-scheme:light dark}body{background:Canvas}${markup.css}</style><section id="codex-context-token-inspector-root" class="cti-hud" style="position:absolute;left:32px;top:32px;bottom:auto;max-height:none;padding:16px">${markup.quota}</section>`);
        for (const colorScheme of ['light', 'dark']) {
          await visual.emulateMedia({colorScheme});
          await visual.screenshot({path: path.join(process.argv[3], engine.name() + '-' + colorScheme + '.png')});
        }
        await visual.close();
      }
      await page.evaluate(() => { Date.now = window.savedNow; delete window.savedNow; });
      delete payload.quota; payload.observedAt = Date.now()/1000;
      await publish();
      assert.ok((await page.locator('[data-quota]').textContent()).includes('暂时无法读取配额'));
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
      await page.evaluate(() => { window.originalUnits = document.querySelector('.cti-unit-group'); });
      for (const language of ['en', 'zh']) {
        await page.locator('[data-language]').selectOption(language);
        assert.equal(await page.locator('[data-settings]').evaluate(node => node.hidden), false, 'language switch must preserve open settings');
        assert.equal(await page.locator('[data-settings-toggle]').getAttribute('aria-expanded'), 'true');
        assert.equal(await page.evaluate(() => document.querySelector('.cti-unit-group') === window.originalUnits), true);
        assert.equal(await page.locator('.cti-unit-group').count(), 1);
      }
      if (process.argv[3]) {
        await page.addStyleTag({content: ':root{color-scheme:light dark}body{background:Canvas}'});
        for (const colorScheme of ['light', 'dark']) {
          await page.emulateMedia({colorScheme});
          await page.locator('.cti-hud').screenshot({path:path.join(process.argv[3],`${engine.name()}-settings-${colorScheme}.png`)});
        }
      }
      payload.build = {pluginVersion: '<b>test</b>'};
      payload.update = {status:'update_available',latestSemver:'2.0.0',url:'https://example.test/release'};
      await publish();
      assert.equal(await page.locator('[data-build] b').count(), 0);
      assert.ok((await page.locator('[data-build]').textContent()).includes('<b>test</b>'));
      assert.ok((await page.locator('[data-dom]').textContent()).includes('未提供'));
      assert.equal(await page.locator('[data-update] a').getAttribute('href'), 'https://example.test/release');
      if(process.argv[3]) {
        await page.addStyleTag({content: ':root{color-scheme:light dark}body{background:Canvas}'});
        for(const colorScheme of ['light','dark']) {
          await page.emulateMedia({colorScheme});
          await page.locator('[data-update]').screenshot({path:path.join(process.argv[3],`${engine.name()}-update-${colorScheme}.png`)});
        }
      }
      delete payload.build; delete payload.update;
      await publish();
      assert.equal(await page.locator('[data-update]').textContent(), '');
      await page.locator('[data-cti-unit="raw"]').click();
      assert.equal(await page.evaluate(() => localStorage.getItem('codex-context-token-inspector-unit')), 'raw');
      assert.equal(await page.locator('[data-context] [role="meter"]').getAttribute('aria-valuenow'), '50');
      for (const [unit, expected] of [['k', '0.50K / 1.00K'], ['m', '0.00M / 0.00M'], ['auto', '500 / 1K'], ['raw', '500 / 1,000']]) {
        await page.locator(`[data-cti-unit="${unit}"]`).click();
        assert.ok((await page.locator('[data-context]').textContent()).includes(expected), unit);
        assert.deepEqual(await page.locator('[data-cti-unit]').evaluateAll(buttons => buttons.map(button => [button.dataset.ctiUnit, button.dataset.active, button.getAttribute('aria-pressed')])),
          ['auto', 'raw', 'k', 'm'].map(value => [value, String(value === unit), String(value === unit)]));
      }

      await page.evaluate(() => {
        window.originalSetItem = Storage.prototype.setItem;
        Storage.prototype.setItem = function(key, value) {
          if (key === 'codex-context-token-inspector-unit') throw new DOMException('Full', 'QuotaExceededError');
          return window.originalSetItem.call(this, key, value);
        };
      });
      await page.locator('[data-cti-unit="k"]').click();
      assert.ok((await page.locator('[data-context]').textContent()).includes('0.50K / 1.00K'));
      assert.equal(await page.locator('[data-cti-unit="k"]').getAttribute('aria-pressed'), 'true');
      assert.equal(await page.evaluate(() => localStorage.getItem('codex-context-token-inspector-unit')), 'raw');
      await page.evaluate(() => { Storage.prototype.setItem = window.originalSetItem; delete window.originalSetItem; });
      await page.locator('[data-cti-unit="auto"]').click();
      assert.equal(await page.evaluate(() => localStorage.getItem('codex-context-token-inspector-unit')), 'auto');
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
