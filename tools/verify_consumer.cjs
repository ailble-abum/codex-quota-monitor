// Initializer lifecycle only, in isolated Chromium/WebKit; no external assets.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium, webkit} = require('playwright');
(async () => {
  const source = fs.readFileSync(path.join(__dirname, '../quota_monitor/page_bridge.js'), 'utf8');
  for (const engine of [chromium, webkit]) {
    const browser = await engine.launch();
    try {
      const page = await browser.newPage();
      const call = options => page.evaluate(({source, options}) => (0, eval)(source)(options), {source, options});
      const options = {action: 'initialize', expected: 'about:blank', key: 'one',
        consumer: {digest: 'synthetic', source: `(empty => {
          window.mounts = (window.mounts || 0) + 1;
          window.__codexContextTokenInspectorUpdate = data => { window.last = data; };
          window.__codexContextTokenInspectorUpdate(empty);
        })`}};
      assert.equal(await call(options), false);
      assert.equal(await page.evaluate(() => window.mounts || 0), 0);
      await page.evaluate(() => { window.__quotaMonitorV2Thread = 'one'; });
      assert.equal(await call({...options, expected: 'http://wrong.invalid'}), false);
      assert.equal(await call({...options, action: 'prepare'}), 'missing');
      assert.equal(await call(options), 'ready');
      assert.equal(await call(options), 'ready');
      assert.equal(await page.evaluate(() => window.mounts), 1);
      assert.deepEqual(await page.evaluate(() => window.last.summaries), []);
      await page.evaluate(() => { delete window.__codexContextTokenInspectorUpdate; });
      await assert.rejects(call(options));
      assert.equal(await page.evaluate(() => window.mounts), 1);
      for (const script of ['(() => { window.mounts = 1; throw Error("private"); })',
        '(() => { window.__codexContextTokenInspectorUpdate = () => {}; throw Error(); })',
        '(() => {})', '42', '(async () => { throw Error("private"); })']) {
        await page.reload();
        await page.evaluate(() => { window.__quotaMonitorV2Thread = 'one'; });
        const errors = [];
        const listener = error => errors.push(error.message);
        page.on('pageerror', listener);
        await assert.rejects(call({...options, consumer: {source: script}}));
        await assert.rejects(call({...options, action: 'prepare'}));
        await assert.rejects(call(options));
        await page.waitForTimeout(30);
        assert.deepEqual(errors, []);
        page.off('pageerror', listener);
      }
      await page.reload();
      await page.evaluate(() => {
        window.__quotaMonitorV2Thread = 'one';
        window.__codexContextTokenInspectorUpdate = () => {};
      });
      assert.equal(await call({...options, consumer: {source: 'throw Error()'}}), 'ready');
      assert.equal(await page.evaluate(() => window.mounts || 0), 0);
      for (const outcome of ['throw Error("private")', 'return false', 'return Promise.reject(Error("private"))']) {
        await page.reload();
        await page.evaluate(() => { window.__quotaMonitorV2Thread = 'one'; });
        const managed = {...options, owner: 'managed', consumer: {source: `(empty => {
          window.__codexContextTokenInspectorUpdate = () => {};
          return {dispose() { ${outcome}; }};
        })`}};
        assert.equal(await call(managed), 'ready');
        await assert.rejects(call({...managed, action: 'release'}));
        await assert.rejects(call({...managed, action: 'prepare'}));
      }
      await page.reload();
      await page.evaluate(() => { window.__quotaMonitorV2Thread = 'one'; });
      assert.equal(await call({...options, owner: 'old', consumer: {source: `(empty => {
        window.disposedCount = 0;
        window.__codexContextTokenInspectorUpdate = () => {};
        return {dispose() { window.disposedCount++; }};
      })`}}), 'ready');
      await page.evaluate(() => { window.__codexContextTokenInspectorUpdate = () => {}; });
      assert.equal(await call({...options, owner: 'old', action: 'release'}), true);
      assert.equal(await page.evaluate(() => window.disposedCount), 0);
      console.log(engine.name() + ': guarded init, empty first paint, reuse, reload, failed/lost hook and existing consumer passed');
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
