// Exercise time passing without new deliveries. Only synthetic account/chat data.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium, webkit} = require('playwright');

(async () => {
  const source = fs.readFileSync(process.argv[2], 'utf8');
  const bridge = fs.readFileSync(path.join(__dirname, '../quota_monitor/page_bridge.js'), 'utf8');
  for (const engine of [chromium, webkit]) {
    const browser = await engine.launch();
    try {
      const page = await browser.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/*', route => route.fulfill({contentType: 'text/html', body: '<html><head></head><body></body></html>'}));
      await page.goto('http://expiry.invalid/');
      await page.clock.install({time: new Date('2026-10-03T00:00:00Z')});
      await page.evaluate(() => {
        localStorage.setItem('cti-language', 'zh');
        localStorage.setItem('codex-context-token-inspector-collapsed', 'true');
        window.__quotaMonitorV2Thread = 'one';
      });
      const base = {expected: 'http://expiry.invalid/', key: 'one', owner: 'expiry'};
      const call = options => page.evaluate(({bridge, options}) => (0, eval)(bridge)(options), {bridge, options});
      const initialize = () => call({...base, action: 'initialize', consumer: {source, digest: 'synthetic-expiry'}});
      const publish = async (age = 0, remaining = 73) => {
        const now = await page.evaluate(() => Date.now() / 1000);
        return call({...base, action: 'publish', panel: true, payload: {
          activeThreadId: 'one', selectedThreadId: 'one', observedAt: now,
          summaries: [{thread_id: 'one', latest_context_percent: 50}],
          quota: {status: 'live', updatedAt: now - age, windows: [{remaining, duration: 300}],
            budget: {kind: 'exhaust', seconds: 900}}
        }});
      };
      const remaining = () => page.locator('[data-quota] [role="meter"]').getAttribute('aria-valuenow');
      const expired = async () => {
        assert.equal(await page.locator('[data-quota] [role="meter"]').count(), 0);
        assert.match(await page.locator('[data-freshness]').textContent(), /账户配额未更新/);
        assert.doesNotMatch(await page.locator('[data-cti-title]').getAttribute('aria-label'), /还能用|73%|61%/);
        assert.equal(await page.locator('.cti-hud').getAttribute('data-tone'), 'unknown');
        assert.equal(await page.locator('[data-gauge]').getAttribute('data-state'), 'empty');
        assert.match(await page.locator('.cti-edge-mascot').getAttribute('aria-label'), /配额暂不可用/);
      };
      assert.equal(await initialize(), 'ready');

      // Switching invalidates the context and stops bridge deliveries. The account
      // remains visible until its own deadline, then must expire without a push.
      assert.equal(await publish(118), true);
      await page.evaluate(() => { window.__quotaMonitorV2Thread = 'two'; });
      await page.clock.runFor(300);
      assert.equal(await page.locator('[data-context] [role="meter"]').count(), 0);
      assert.equal(await remaining(), '73');
      await page.clock.runFor(1800);
      await expired();

      // While the thread stays selected, quota may age out before the context lease.
      await page.evaluate(() => { window.__quotaMonitorV2Thread = 'one'; });
      assert.equal(await publish(119), true);
      await page.clock.runFor(1100);
      await expired();
      assert.equal(await page.locator('[data-context] [role="meter"]').getAttribute('aria-valuenow'), '50');

      // A newer account sample replaces the old expiry deadline; stop new pushes.
      assert.equal(await publish(119), true);
      await page.clock.runFor(500);
      assert.equal(await publish(0, 61), true);
      await page.clock.runFor(700);
      assert.equal(await remaining(), '61');
      await page.clock.fastForward(120000);
      await expired();

      // Disposal with a pending expiry callback must not recreate the panel.
      assert.equal(await publish(119), true);
      assert.equal(await call({...base, action: 'release'}), true);
      await page.clock.runFor(1500);
      assert.equal(await page.locator('.cti-hud,.cti-edge-mascot').count(), 0);
      assert.equal(await page.evaluate(() => typeof window.__codexContextTokenInspectorUpdate), 'undefined');
      assert.deepEqual(errors, []);
      console.log(`${engine.name()}: switch, account-only expiry, newer sample, suspended timers and disposal passed`);
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
