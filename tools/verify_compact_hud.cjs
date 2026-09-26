// Offline compact-HUD probe using only synthetic account and session data.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium, webkit} = require('playwright');

async function main() {
  const [consumerPath, artifacts] = process.argv.slice(2);
  assert.ok(consumerPath && artifacts, 'Usage: node tools/verify_compact_hud.cjs CONSUMER ARTIFACT_DIR');
  const source = fs.readFileSync(consumerPath, 'utf8');
  const bridge = fs.readFileSync(path.join(__dirname, '../quota_monitor/page_bridge.js'), 'utf8');
  fs.mkdirSync(artifacts, {recursive: true});

  for (const engine of [chromium, webkit]) {
    const browser = await engine.launch();
    try {
      const context = await browser.newContext({viewport:{width:900, height:600}, locale:'zh-CN'});
      const page = await context.newPage();
      const unexpected = [];
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/*', route => {
        if (route.request().url() !== 'http://compact.invalid/') unexpected.push(route.request().url());
        return route.fulfill({contentType:'text/html', body:'<!doctype html><html lang="zh-CN"><body></body></html>'});
      });
      await page.goto('http://compact.invalid/');
      await page.evaluate(() => {
        localStorage.setItem('cti-language', 'zh');
        localStorage.setItem('codex-context-token-inspector-collapsed', 'true');
        window.__quotaMonitorV2Thread = 'synthetic';
      });
      const call = options => page.evaluate(({bridge, options}) => (0, eval)(bridge)(options), {bridge, options});
      const base = {expected:'http://compact.invalid/', key:'synthetic'};
      assert.equal(await call({...base, action:'initialize', consumer:{source, digest:'compact-synthetic'}}), 'ready');

      const now = Date.now() / 1000;
      const payload = {
        activeThreadId:'synthetic', selectedThreadId:'synthetic', observedAt:now,
        summaries:[{thread_id:'synthetic', latest_context_percent:37}],
        detailsByThread:{}, healthThreadId:'synthetic',
        health:{count:3, after:52300, afterPercent:20.2},
        quota:{status:'live', accountKey:'synthetic-account', updatedAt:now,
          windows:[{key:'weekly', duration:10080, remaining:62}]},
      };
      const publish = () => call({...base, action:'publish', payload, panel:true});
      assert.equal(await publish(), true);
      const strong = await page.locator('.cti-mini strong').allTextContents();
      const sub = await page.locator('.cti-mini em').allTextContents();
      assert.deepEqual(strong, ['62%', '37%']);
      assert.deepEqual(sub, ['↻3 · 压后 20.2%']);
      assert.ok(!(await page.locator('[data-cti-title]').innerText()).includes('52.3K'));
      const oneWindowWidth = await page.locator('.cti-hud').evaluate(node => node.getBoundingClientRect().width);
      assert.ok(oneWindowWidth >= 195 && oneWindowWidth <= 215, `unexpected one-window width ${oneWindowWidth}`);
      const oneWindowTitle = await page.locator('[data-cti-title]').evaluate(node => ({scroll:node.scrollWidth, client:node.clientWidth}));
      assert.ok(oneWindowTitle.scroll <= oneWindowTitle.client + 1, `clipped one-window title ${JSON.stringify(oneWindowTitle)}`);
      const toggleGeometry = await page.locator('[data-cti-toggle]').evaluate(node => {
        const button = node.getBoundingClientRect();
        const header = node.closest('.cti-header').getBoundingClientRect();
        const icon = getComputedStyle(node, '::before');
        return {centers:[button.top + button.height / 2, header.top + header.height / 2], size:[node.clientWidth, node.clientHeight],
          icon:{left:icon.left, top:icon.top, transform:icon.transform}};
      });
      assert.ok(Math.abs(toggleGeometry.centers[0] - toggleGeometry.centers[1]) <= 1,
        `toggle box is off-center ${JSON.stringify(toggleGeometry)}`);
      assert.equal(parseFloat(toggleGeometry.icon.left), toggleGeometry.size[0] / 2);
      assert.equal(parseFloat(toggleGeometry.icon.top), toggleGeometry.size[1] / 2);
      assert.equal(toggleGeometry.icon.transform, 'matrix(1, 0, 0, 1, -5, -0.75)');
      await page.locator('.cti-hud').screenshot({path:path.join(artifacts, `${engine.name()}-one-window-no-estimate.png`)});

      payload.quota.windows[0].exhaustInSec = 31680;
      assert.equal(await publish(), true);
      assert.deepEqual(await page.locator('.cti-mini strong').allTextContents(), ['62%', '37%']);
      assert.deepEqual(await page.locator('.cti-mini em').allTextContents(), ['约 8.8h', '↻3 · 压后 20.2%']);
      assert.ok(await page.locator('[data-cti-title]').evaluate(node => node.scrollWidth <= node.clientWidth + 1));
      await page.locator('.cti-hud').screenshot({path:path.join(artifacts, `${engine.name()}-one-window.png`)});

      payload.quota.windows.unshift({key:'five-hour', duration:300, remaining:84});
      assert.equal(await publish(), true);
      assert.equal(await page.locator('.cti-mini').count(), 3);
      const twoWindowWidth = await page.locator('.cti-hud').evaluate(node => node.getBoundingClientRect().width);
      assert.ok(twoWindowWidth > oneWindowWidth && twoWindowWidth <= 285, `unexpected two-window width ${twoWindowWidth}`);
      assert.ok(await page.locator('[data-cti-title]').evaluate(node => node.scrollWidth <= node.clientWidth + 1));
      await page.locator('.cti-hud').screenshot({path:path.join(artifacts, `${engine.name()}-two-windows.png`)});

      payload.quota = {status:'unavailable', windows:[]};
      payload.summaries = [{thread_id:'synthetic'}];
      payload.health = {count:1, afterPercent:null};
      assert.equal(await publish(), true);
      assert.deepEqual(await page.locator('.cti-mini strong').allTextContents(), ['—']);
      assert.deepEqual(await page.locator('.cti-mini em').allTextContents(), ['↻1 · 压后 …']);
      assert.ok(await page.locator('[data-cti-title]').evaluate(node => node.scrollWidth <= node.clientWidth + 1));

      await page.evaluate(() => {
        const root = document.querySelector('.cti-hud');
        root.__ctiLayout.compact = {...root.__ctiLayout.compact, width:250};
        root.__ctiApplyPosition();
      });
      assert.equal(await page.locator('.cti-hud').evaluate(node => node.style.width), '250px');
      assert.ok(await page.locator('[data-cti-title]').evaluate(node => node.scrollWidth <= node.clientWidth + 1));
      await page.locator('.cti-hud').screenshot({path:path.join(artifacts, `${engine.name()}-unknown-scaled.png`)});
      assert.deepEqual(errors, []);
      assert.deepEqual(unexpected, []);
      await context.close();
      console.log(`${engine.name()}: compact quota, health, window count, unknown data and scale passed`);
    } finally {
      await browser.close();
    }
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
