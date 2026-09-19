// Managed renderer disposal in isolated engines, including actual retained resources.
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
      await page.route('**/*', route => route.fulfill({contentType: 'text/html', body: '<html><head></head><body></body></html>'}));
      await page.goto('http://dispose.invalid/');
      await page.evaluate(() => {
        window.__quotaMonitorV2Thread = 'one';
        window.tracked = new Map();
        window.listenerCount = () => [...tracked.values()].reduce((n, set) => n + set.size, 0);
        window.clearedTimers = [];
        const clear = window.clearTimeout;
        window.clearTimeout = id => { clearedTimers.push(id); return clear(id); };
        const add = window.addEventListener, remove = window.removeEventListener;
        const types = ['pointermove', 'pointerup', 'pointercancel', 'resize'];
        window.addEventListener = function(type, fn, opts) { if (types.includes(type)) { if (!tracked.has(type)) tracked.set(type, new Set()); tracked.get(type).add(fn); } return add.call(this,type,fn,opts); };
        window.removeEventListener = function(type, fn, opts) { if (types.includes(type)) tracked.get(type)?.delete(fn); return remove.call(this,type,fn,opts); };
      });
      const call = options => page.evaluate(({bridge, options}) => (0, eval)(bridge)(options), {bridge, options});
      const base = {expected: 'http://dispose.invalid/', key: 'one', owner: 'A'};
      const initialize = () => call({...base, action: 'initialize', consumer: {source: script, digest: 'fixture'}});
      const publish = owner => call({...base, owner, action: 'publish', panel: true, payload: {
        activeThreadId: 'one', selectedThreadId: 'one', observedAt: Date.now()/1000,
        summaries: [{thread_id: 'one', latest_context_tokens: 50, context_window: 100, latest_context_percent: 50}]}});
      const count = () => page.evaluate(() => document.querySelectorAll('.cti-hud,.cti-edge-mascot,#codex-context-token-inspector-style').length);
      assert.equal(await initialize(), 'ready');
      assert.equal(await count(), 3);
      assert.equal(await page.evaluate(() => listenerCount()), 4);
      await page.evaluate(() => { window.oldHook = window.__codexContextTokenInspectorUpdate; });
      // Initialization-only shutdown must also dispose, before any delivery exists.
      assert.equal(await call({...base, action: 'release'}), true);
      assert.equal(await count(), 0);
      assert.equal(await page.evaluate(() => window.__codexContextTokenInspectorPayload), undefined);
      assert.equal(await page.evaluate(() => listenerCount()), 0);
      await assert.rejects(page.evaluate(() => window.oldHook({summaries: []})));
      assert.equal(await initialize(), 'ready');
      assert.equal(await publish('A'), true);
      assert.equal(await publish('B'), true);
      assert.equal(await call({...base, action: 'release'}), true);
      assert.equal(await count(), 3); // new delivery owner protects the renderer
      await page.evaluate(() => {
        const mascot = document.querySelector('.cti-edge-mascot');
        const root = document.querySelector('.cti-hud');
        root.dataset.docked = 'true'; root.dataset.dockPinned = 'false';
        mascot.dispatchEvent(new PointerEvent('pointerenter'));
        root.dataset.docked = 'true'; // pointerenter may restore the saved undocked layout
        mascot.setPointerCapture = () => {}; // synthetic pointer has no native capture target
        mascot.dispatchEvent(new PointerEvent('pointerdown', {button: 0}));
        root.dispatchEvent(new PointerEvent('pointerleave'));
        window.ownedTimers = [root.__ctiDockHideTimer, mascot.__ctiPetTimer, mascot.__ctiReactionTimer];
        window.originalMascot = mascot;
        const other = document.createElement('button');
        other.id = mascot.id; other.textContent = 'Other mascot';
        mascot.replaceWith(other);
      });
      assert.equal(await page.evaluate(() => ownedTimers.every(id => typeof id === 'number')), true);
      assert.equal(await call({...base, owner: 'B', action: 'release'}), true);
      assert.equal(await page.evaluate(() => ownedTimers.every(id => clearedTimers.includes(id))), true);
      assert.equal(await page.evaluate(() => document.querySelector('#codex-context-token-inspector-mascot').textContent), 'Other mascot');
      assert.equal(await page.evaluate(() => listenerCount()), 0);
      await page.waitForTimeout(1600); // pending reaction/pet/dock callbacks must not recreate UI
      assert.equal(await page.evaluate(() => document.querySelectorAll('.cti-hud,#cti-context-hint').length), 0);
      assert.equal(await page.evaluate(() => window.__codexContextTokenInspectorUpdate), undefined);
      assert.equal(await call({...base, owner: 'B', action: 'release'}), true);
      console.log(engine.name() + ': init-only dispose, listener cleanup, remount, ownership transfer, foreign mascot and no resurrection passed');
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
