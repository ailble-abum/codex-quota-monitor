// Synthetic pointer/layout regression. No installed monitor or real sessions.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium, webkit} = require('playwright');
const source = fs.readFileSync(process.argv[2], 'utf8');
const bridge = fs.readFileSync(path.join(__dirname, '../quota_monitor/page_bridge.js'), 'utf8');
const failures = [];
const settle = page => page.waitForFunction(() => {
  const r = document.querySelector('.cti-hud'), box = r.getBoundingClientRect();
  return Math.abs(box.x - parseFloat(r.style.left)) < 1 && Math.abs(box.y - parseFloat(r.style.top)) < 1;
});
const readyAfterDrag = page => page.waitForFunction(() => performance.now() >
  (document.querySelector('.cti-hud').__ctiSuppressClickUntil || 0));
const cases = {
  async 'floating edge preference'(page, root) {
    await page.locator('[data-settings-toggle]').click();
    await page.locator('[data-edge-dock]').uncheck();
    await page.locator('[data-cti-toggle]').click();
    await settle(page);
    assert.ok(Math.abs((await root.boundingBox()).y - 720) < 1, 'preference must retain lower anchor');
  },
  async 'pointer resize'(page, root) {
    const box = await page.locator('[data-resize="se"]').boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    assert.equal(await root.evaluate(n => n.__ctiGesture?.resize), 'se', 'pointer must reach resize handle');
    await page.mouse.move(box.x + box.width / 2 + 24, box.y + box.height / 2, {steps:4});
    await page.mouse.up();
    await readyAfterDrag(page);
    await page.locator('[data-cti-toggle]').click();
    await settle(page);
    assert.equal(await root.getAttribute('data-collapsed'), 'true');
    assert.ok(Math.abs((await root.boundingBox()).y - 720) < 1, `width change must retain lower anchor: ${JSON.stringify(await root.evaluate(n => ({layout:n.__ctiLayout, box:n.getBoundingClientRect().toJSON(), collapsed:n.dataset.collapsed})))}`);
  },
  async 'compact saved fallback'(page, root) {
    await page.locator('[data-cti-toggle]').click();
    await settle(page);
    assert.ok(Math.abs((await root.boundingBox()).y - 720) < 1, 'first collapse must retain fallback compact anchor');
  },
  async 'keyboard resize'(page, root) {
    await page.locator('[data-resize="se"]').focus();
    await page.keyboard.press('ArrowRight');
    await page.locator('[data-cti-toggle]').click();
    await settle(page);
    assert.ok(Math.abs((await root.boundingBox()).y - 720) < 1, 'keyboard width change must retain lower anchor');
  },
  async 'docked click'(page, root) {
    await page.locator('[data-cti-title]').click();
    assert.equal(await root.getAttribute('data-docked'), 'true', 'click without movement must keep docking');
    assert.equal(await root.evaluate(n => n.__ctiLayout.expanded.y), 720);
  },
  async 'docked resize'(page, root) {
    await page.locator('[data-resize="se"]').focus();
    await page.keyboard.press('ArrowRight');
    assert.equal(await root.evaluate(n => n.__ctiLayout.expanded.y), 720, 'resize must not copy clamped panel top to mascot');
  },
  async 'docked companion drag'(page, root) {
    const mascot = page.locator('#codex-context-token-inspector-mascot');
    const box = await mascot.boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height * .8);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height * .8 + 12, {steps:3});
    await page.mouse.up();
    assert.ok(Math.abs((await mascot.boundingBox()).y - (box.y + 12)) < 1, 'companion drag must follow pointer, independent of expanded height');
  },
  async 'cancel panel drag'(page, root) {
    const before = await root.evaluate(n => JSON.stringify(n.__ctiLayout));
    const stored = await page.evaluate(() => localStorage.getItem('cti-layout-v2'));
    const box = await page.locator('[data-cti-title]').boundingBox();
    await page.mouse.move(box.x + 10, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + 50, box.y + box.height / 2 + 12, {steps:3});
    const pointerId = await root.evaluate(n => n.__ctiGesture?.pointerId || 1);
    await root.dispatchEvent('pointercancel', {pointerId, pointerType:'mouse', bubbles:true});
    await page.mouse.up();
    assert.equal(await root.evaluate(n => JSON.stringify(n.__ctiLayout)), before, 'cancel must restore unsaved layout');
    assert.equal(await page.evaluate(() => localStorage.getItem('cti-layout-v2')), stored, 'cancel must not save intermediate position');
  },
};
cases['docked cancel panel drag'] = cases['cancel panel drag'];
cases['docked disable edge preference'] = cases['floating edge preference'];
(async () => {
  for (const engine of [chromium, webkit]) {
    const browser = await engine.launch();
    try {
      for (const reducedMotion of ['reduce', 'no-preference']) for (const [name, check] of Object.entries(cases)) {
        const page = await browser.newPage({viewport:{width:1100,height:850}, reducedMotion});
        const errors = []; page.on('pageerror', e => errors.push(e.message));
        try {
          await page.route('**/*', route => route.fulfill({contentType:'text/html', body:'<!doctype html><html><body></body></html>'}));
          await page.goto('http://position.invalid/');
          await page.evaluate(name => {
            window.__quotaMonitorV2Thread = 'position';
            localStorage.setItem('cti-language', 'zh');
            localStorage.setItem('cti-mascot-scale', '1');
            const anchor = {x:350, y:720, ...(name.startsWith('docked') ? {edge:'left'} : {})};
            localStorage.setItem('cti-layout-v2', JSON.stringify({compact:anchor, ...(name === 'compact saved fallback' ? {} : {expanded:anchor})}));
          }, name);
          const call = options => page.evaluate(({bridge, options}) => (0,eval)(bridge)(options), {bridge, options});
          const base = {expected:'http://position.invalid/', key:'position'};
          assert.equal(await call({...base, action:'initialize', consumer:{source}}), 'ready');
          await call({...base, action:'publish', panel:true, payload:{activeThreadId:'position', observedAt:Date.now()/1000,
            summaries:[], quota:{status:'live', updatedAt:Date.now()/1000, windows:[{duration:10080, remaining:86}]}}});
          const root = page.locator('.cti-hud');
          if (name.startsWith('docked')) await page.locator('#codex-context-token-inspector-mascot').click();
          await settle(page);
          assert.ok((await root.boundingBox()).y < 620, 'fixture must clamp expanded panel above saved anchor');
          await check(page, root);
          assert.deepEqual(errors, []);
          console.log(`${engine.name()} ${reducedMotion} ${name}: passed`);
        } catch (e) {
          failures.push(`${engine.name()} ${reducedMotion} ${name}: ${e.message}`);
        } finally { await page.close(); }
      }
    } finally { await browser.close(); }
  }
  assert.deepEqual(failures, []);
})().catch(e => { console.error(e); process.exitCode = 1; });
