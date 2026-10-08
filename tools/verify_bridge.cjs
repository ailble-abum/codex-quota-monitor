// Synthetic page contract; no installed app or user data is accessed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium, webkit } = require('playwright');

async function main() {
  const source = fs.readFileSync(path.join(__dirname, '../quota_monitor/page_bridge.js'), 'utf8');
  for (const engine of [chromium, webkit]) {
    const browser = await engine.launch();
    try {
      const page = await browser.newPage();
      page.setDefaultTimeout(5000);
      const call = options => page.evaluate(({source, options}) => (0, eval)(source)(options), {source, options});
      await page.evaluate(() => {
        window.deliveries = [];
        window.__codexContextTokenInspectorUpdate = data => window.deliveries.push(data);
      });
      const options = {action: 'publish', expected: 'about:blank', key: 'one',
        payload: {activeThreadId: 'one', summaries: [{thread_id: 'one'}]}, host: 'explicit', panel: true};
      assert.equal(await call(options), false);
      assert.equal(await page.evaluate(() => window.deliveries.length), 0);
      await page.evaluate(() => { window.__quotaMonitorV2Thread = 'one'; });
      assert.equal(await call(options), true);
      assert.equal(await page.evaluate(() => window.deliveries.length), 1);
      await page.evaluate(() => { window.__quotaMonitorV2Thread = 'two'; });
      await page.waitForFunction(() => window.deliveries.at(-1).summaries.length === 0);
      assert.equal(await page.evaluate(() => window.__quotaMonitorV2Snapshot), null);
      await page.evaluate(() => { window.__quotaMonitorV2Thread = 'one'; });
      assert.equal(await page.evaluate(() => window.__quotaMonitorV2Snapshot), null);
      assert.equal(await call(options), true);
      await page.evaluate(() => { performance.now = () => 1e15; });
      await page.waitForFunction(() => window.deliveries.at(-1).summaries.length === 0);
      const count = await page.evaluate(() => window.deliveries.length);
      await page.waitForTimeout(600);
      assert.equal(await page.evaluate(() => window.deliveries.length), count);
      await page.evaluate(() => { delete performance.now; });
      assert.equal(await call(options), true);
      await page.evaluate(() => { window.__codexContextTokenInspectorUpdate = () => { throw Error('private'); }; });
      await assert.rejects(call(options));
      await page.waitForFunction(() => window.deliveries.at(-1).summaries.length === 0);
      await page.evaluate(() => {
        window.__codexContextTokenInspectorUpdate = data => window.deliveries.push(data);
      });
      assert.equal(await call(options), true);
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.evaluate(() => Object.defineProperty(window, '__codexContextTokenInspectorUpdate', {
        configurable: true, get() { throw Error('private getter'); }
      }));
      await page.waitForFunction(() => window.deliveries.at(-1).summaries.length === 0);
      await page.waitForTimeout(600);
      assert.deepEqual(errors, []);
      await page.evaluate(() => Object.defineProperty(window, '__codexContextTokenInspectorUpdate', {
        configurable: true, writable: true, value: data => window.deliveries.push(data)
      }));
      assert.equal(await call(options), true);
      await page.evaluate(() => { performance.now = () => { throw Error('clock'); }; });
      await assert.rejects(call(options));
      await page.waitForFunction(() => window.deliveries.at(-1).summaries.length === 0);
      await page.evaluate(() => { delete performance.now; });
      assert.deepEqual(errors, []);
      assert.equal(await call(options), true);
      await page.evaluate(() => { window.__quotaMonitorV2Delivery.stop(); window.__quotaMonitorV2Thread = null; });
      assert.equal(await call({action: 'invalidate', expected: 'about:blank'}), true);
      assert.equal(await page.evaluate(() => window.deliveries.at(-1).summaries.length), 0);
      assert.equal(await page.evaluate(() => window.__quotaMonitorV2Snapshot), null);
      const readHost = () => call({action: 'read', expected: 'about:blank', host: 'codex-sidebar'});
      await page.setContent('<button data-app-action-sidebar-thread-row data-app-action-sidebar-thread-id="local:one" data-app-action-sidebar-thread-host-id="local" data-app-action-sidebar-thread-kind="local" data-app-action-sidebar-thread-active="true"></button>');
      assert.equal(await readHost(), 'one');
      await page.evaluate(() => {
        const inactive = document.createElement('section');
        inactive.id = 'inactive-shell'; inactive.dataset.appShellActivePage = 'false';
        const oldRow = document.querySelector('button').cloneNode();
        oldRow.setAttribute('data-app-action-sidebar-thread-id', 'old-thread');
        inactive.append(oldRow); document.body.append(inactive);
      });
      assert.equal(await readHost(), 'one', 'cached inactive Codex page must not make the current task ambiguous');
      await page.evaluate(() => { document.getElementById('inactive-shell').dataset.appShellActivePage = 'true'; });
      assert.equal(await readHost(), null, 'two active pages remain ambiguous');
      await page.evaluate(() => {
        document.getElementById('inactive-shell').dataset.appShellActivePage = 'false';
        document.querySelector('body > button').remove();
      });
      assert.equal(await readHost(), null, 'never use the inactive task when no live row exists');
      await page.evaluate(() => {
        const inactive = document.getElementById('inactive-shell');
        const row = inactive.querySelector('button');
        row.setAttribute('data-app-action-sidebar-thread-id', 'local:one');
        document.body.append(row); inactive.remove();
      });
      await page.evaluate(() => {
        const row = document.querySelector('button').cloneNode();
        row.setAttribute('data-app-action-sidebar-thread-active', 'false');
        row.setAttribute('data-app-action-sidebar-thread-selected', 'true');
        row.setAttribute('data-app-action-sidebar-thread-id', 'two');
        document.body.append(row);
      });
      assert.equal(await readHost(), 'one');
      const readHover = () => call({action:'sidebarHover', expected:'about:blank', host:'codex-sidebar', key:'one'});
      await page.evaluate(() => { window.__quotaMonitorV2SidebarThread = 'local:two'; });
      assert.equal(await readHover(), 'two');
      await page.locator('button:last-child').evaluate(row => row.setAttribute('data-app-action-sidebar-thread-host-id', 'remote-host'));
      assert.equal(await readHover(), null, 'remote hover must not request local logs');
      await page.locator('button:last-child').evaluate(row => {
        row.setAttribute('data-app-action-sidebar-thread-host-id', 'local');
        const shell=document.createElement('section'); shell.dataset.appShellActivePage='false';
        row.replaceWith(shell); shell.append(row);
      });
      assert.equal(await readHover(), null, 'inactive hover must not request local logs');
      await page.evaluate(() => {
        const shell=document.querySelector('section'); const row=shell.querySelector('button');
        shell.replaceWith(row); window.__quotaMonitorV2SidebarThread='missing';
      });
      assert.equal(await readHover(), null, 'missing row must not request local logs');
      await page.evaluate(() => document.querySelector('button:last-child').remove());
      await page.evaluate(() => document.body.append(document.querySelector('button').cloneNode()));
      assert.equal(await readHost(), null);
      await page.evaluate(() => document.querySelector('button').remove());
      await page.evaluate(() => {
        const row = document.querySelector('button');
        row.setAttribute('data-app-action-sidebar-thread-id', 'local:client-new-thread:alias-one');
        const portal = document.createElement('div');
        portal.dataset.aboveComposerPortal = '';
        portal.dataset.aboveComposerConversationId = 'one';
        document.body.append(portal);
      });
      assert.equal(await readHost(), 'one', 'new-thread alias must use the resolved active composer ID');
      await page.evaluate(() => { window.__quotaMonitorV2SidebarThread = 'one'; });
      assert.equal(await readHover(), 'one', 'hovering the resolved active alias must request its own journal');
      await page.evaluate(() => document.querySelector('[data-above-composer-portal]')
        .setAttribute('data-above-composer-conversation-id', 'chatgpt:chat-one'));
      assert.equal(await readHost(), null, 'ChatGPT must never read a local journal');
      assert.equal(await call({action:'contextSource', expected:'about:blank', host:'codex-sidebar'}), 'chatgpt');
      await page.evaluate(() => {
        const row = document.querySelector('button').cloneNode();
        row.id = 'local-work-hover';
        row.setAttribute('data-app-action-sidebar-thread-id', 'local:two');
        row.setAttribute('data-app-action-sidebar-thread-active', 'false');
        document.body.append(row);
        window.__quotaMonitorV2SidebarThread = 'two';
      });
      assert.equal(await call({action:'sidebarHover', expected:'about:blank', host:'codex-sidebar', key:null}), 'two',
        'local Work hover must remain readable while no local chat is active');
      await page.evaluate(() => document.getElementById('local-work-hover').remove());
      const accountOptions = {...options, host:'codex-sidebar', key:null,
        payload:{activeThreadId:null, selectedThreadId:null, summaries:[],
          quota:{status:'live',updatedAt:Date.now()/1000,windows:[{remaining:75}]}}};
      assert.equal(await call(accountOptions), true, 'account publication must work without a local task');
      assert.equal(await page.evaluate(() => window.__quotaMonitorV2Snapshot.quota.windows[0].remaining), 75);
      await page.evaluate(() => {
        const portal = document.querySelector('[data-above-composer-portal]');
        portal.dataset.aboveComposerConversationId = 'one';
        document.body.append(portal.cloneNode());
      });
      assert.equal(await readHost(), null, 'two active composers are ambiguous');
      await page.evaluate(() => {
        document.querySelector('[data-above-composer-portal]').remove();
        const portal = document.querySelector('[data-above-composer-portal]');
        const shell = document.createElement('section');
        shell.dataset.appShellActivePage = 'false';
        portal.replaceWith(shell); shell.append(portal);
      });
      assert.equal(await readHost(), null, 'an alias cannot use a hidden composer');
      await page.evaluate(() => {
        document.querySelector('section').remove();
        document.querySelector('button').setAttribute('data-app-action-sidebar-thread-id', 'local:one');
      });
      for (const [attribute, value] of [['kind', 'remote'], ['host-id', 'remote-host'],
        ['host-id', ''], ['id', 'invalid/key'], ['id', 'one\n'], ['active', 'false']]) {
        const name = 'data-app-action-sidebar-thread-' + attribute;
        const before = await page.locator('button').getAttribute(name);
        await page.locator('button').evaluate((node, {name, value}) => node.setAttribute(name, value), {name, value});
        assert.equal(await readHost(), null);
        await page.locator('button').evaluate((node, {name, before}) => node.setAttribute(name, before), {name, before});
      }
      await page.setContent('');
      assert.equal(await readHost(), null); // Never falls back to explicit opt-in or a selected row.
      await page.evaluate(() => { window.__quotaMonitorV2Thread = 'one'; });
      assert.equal(await call(options), true);
      assert.equal(await call({action: 'release', expected: 'about:blank', owner: 'different'}), true);
      assert.equal(await page.evaluate(() => Boolean(window.__quotaMonitorV2Snapshot)), true);
      assert.equal(await call({action: 'release', expected: 'about:blank'}), true);
      assert.equal(await page.evaluate(() => Object.hasOwn(window, '__quotaMonitorV2Snapshot')), false);
      assert.equal(await page.evaluate(() => Object.hasOwn(window, '__quotaMonitorV2Delivery')), false);
      assert.equal(await page.evaluate(() => window.deliveries.at(-1).summaries.length), 0);
      assert.equal(await call(options), true);
      await page.evaluate(() => Object.defineProperty(window, '__quotaMonitorV2Snapshot', {configurable: false}));
      await assert.rejects(call(options));
      await page.evaluate(() => { window.__quotaMonitorV2Thread = 'two'; });
      await page.waitForFunction(() => window.deliveries.at(-1).summaries.length === 0);
      assert.deepEqual(errors, []);
      await page.close();
      console.log(`${engine.name()}: no opt-in, delivery, switch clear, expiry clear, no repeat, consumer error, local host identity, selected-vs-active, ambiguity passed`);
    } finally { await browser.close(); }
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
