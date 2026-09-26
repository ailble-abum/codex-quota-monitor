// Synthetic browser regression for the docked companion, compact panel, and quota gauge.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium, webkit} = require('playwright');

const [consumerPath, artifacts] = process.argv.slice(2);
assert.ok(consumerPath && artifacts,
  'Usage: node tools/verify_edge_interaction.cjs CONSUMER ARTIFACT_DIR');
const source = fs.readFileSync(consumerPath, 'utf8');
const bridge = fs.readFileSync(path.join(__dirname, '../quota_monitor/page_bridge.js'), 'utf8');
const skins = {
  candy:[23, 294], cat:[0, 320], corgi:[0, 320],
  frost:[66, 297], mint:[101, 317], tea:[86, 320],
};

const quotaWindows = [
  {key:'five-hour', duration:300, remaining:76, exhaustInSec:18400},
  {key:'weekly', duration:10080, remaining:43, exhaustInSec:221000},
];

async function publish(page, call, base, windows = quotaWindows) {
  const now = Date.now() / 1000;
  return call({...base, action:'publish', panel:true, payload:{
    activeThreadId:'synthetic', selectedThreadId:'synthetic', observedAt:now,
    summaries:[{thread_id:'synthetic', latest_context_percent:41}],
    quota:{status:'live', accountKey:'synthetic-account', updatedAt:now,
      windows},
  }});
}

async function main() {
  fs.mkdirSync(artifacts, {recursive:true});
  for (const engine of [chromium, webkit]) {
    const browser = await engine.launch();
    try {
      for (const edge of ['left', 'right']) {
        const context = await browser.newContext({
          viewport:{width:1100, height:780}, locale:'zh-CN', reducedMotion:'no-preference',
        });
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/*', route => route.fulfill({
          contentType:'text/html', body:'<!doctype html><html lang="zh-CN"><body></body></html>',
        }));
        await page.goto('http://edge-interaction.invalid/');
        await page.evaluate(edge => {
          window.__quotaMonitorV2Thread = 'synthetic';
          localStorage.setItem('cti-language', 'zh');
          localStorage.setItem('cti-edge-dock', 'true');
          localStorage.setItem('cti-mascot-skin', 'cat');
          localStorage.setItem('codex-context-token-inspector-collapsed', 'true');
          localStorage.setItem('cti-layout-v2', JSON.stringify({
            compact:{edge, y:180, width:270}, expanded:{edge, y:180, width:330},
          }));
        }, edge);
        const call = options => page.evaluate(
          ({bridge, options}) => (0, eval)(bridge)(options), {bridge, options});
        const base = {expected:'http://edge-interaction.invalid/', key:'synthetic'};
        assert.equal(await call({...base, action:'initialize', consumer:{source}}), 'ready');
        assert.equal(await publish(page, call, base), true);
        const root = page.locator('.cti-hud');
        const mascot = page.locator('#codex-context-token-inspector-mascot');
        const gauge = mascot.locator('[data-gauge]');
        const art = mascot.locator('.cti-mascot-art');
        const toggle = root.locator('[data-cti-toggle]');
        assert.equal(await root.getAttribute('data-revealed'), 'false');
        assert.equal(await root.getAttribute('data-collapsed'), 'true');
        assert.ok(Math.abs((await mascot.boundingBox()).y - 180) < 1);
        // Geometry assertions sample final positions, not the intentionally
        // animated path between them.
        await page.emulateMedia({reducedMotion:'reduce'});

        for (const [skin, [alphaLeft, alphaRight]] of Object.entries(skins)) {
          for (const scale of [.75, 1, 1.5, 2]) {
            await page.evaluate(({skin, scale}) => {
              localStorage.setItem('cti-mascot-skin', skin);
              localStorage.setItem('cti-mascot-scale', String(scale));
              document.querySelector('.cti-hud').__ctiApplyPosition();
            }, {skin, scale});
            const artRect = await art.boundingBox();
            const gaugeRect = await gauge.boundingBox();
            const visibleBoundary = edge === 'right'
              ? artRect.x + artRect.width * alphaLeft / 320
              : artRect.x + artRect.width * alphaRight / 320;
            const gaugeBoundary = edge === 'right'
              ? gaugeRect.x + gaugeRect.width : gaugeRect.x;
            const gap = edge === 'right'
              ? visibleBoundary - gaugeBoundary : gaugeBoundary - visibleBoundary;
            assert.ok(Math.abs(gap - 4 * scale) < .45,
              `${engine.name()} ${edge} ${skin} ${scale}: unexpected gauge gap ${gap}`);
            assert.ok(Math.abs((await mascot.boundingBox()).y - 180) < 1,
              `${engine.name()} ${edge} ${skin} ${scale}: mascot Y anchor moved`);
            const panelRect = await root.boundingBox();
            const mascotRect = await mascot.boundingBox();
            assert.ok(Math.abs(panelRect.y + panelRect.height / 2
              - mascotRect.y - mascotRect.height / 2) <= 1,
            `${engine.name()} ${edge} ${skin} ${scale}: compact centers differ`);
            if (edge === 'right' && skin === 'tea' && [0.75, 2].includes(scale)) {
              await mascot.hover();
              await page.screenshot({path:path.join(artifacts,
                `${engine.name()}-right-tea-scale-${String(scale).replace('.', '')}-compact-revealed.png`)});
              await page.mouse.move(550, 740);
              await page.evaluate(() => {
                const root = document.querySelector('.cti-hud');
                clearTimeout(root.__ctiDockHideTimer);
                root.dataset.revealed = 'false';
                root.__ctiApplyPosition();
              });
            }
          }
          await page.evaluate(() => {
            localStorage.setItem('cti-mascot-scale', '1');
            document.querySelector('.cti-hud').__ctiApplyPosition();
          });
          await page.screenshot({path:path.join(
            artifacts, `${engine.name()}-${edge}-${skin}-compact.png`)});
        }

        // Stress independent compact widths and content heights at both safe
        // boundaries. The mascot keeps its own stored anchor; only the compact
        // panel is centered and then clamped by its own height.
        for (let windowCount = 0; windowCount <= 2; windowCount++) {
          assert.equal(await publish(page, call, base, quotaWindows.slice(0, windowCount)), true);
          for (const scale of [.75, 1, 1.5, 2]) {
            for (const compactWidth of [180, 360]) {
             for (const requestedY of [0, 260, 10000]) {
              await page.evaluate(({edge, scale, requestedY, compactWidth}) => {
                const root = document.querySelector('.cti-hud');
                localStorage.setItem('cti-mascot-scale', String(scale));
                root.__ctiLayout.compact = {edge, y:requestedY, width:compactWidth};
                root.__ctiApplyPosition();
              }, {edge, scale, requestedY, compactWidth});
              const panelRect = await root.boundingBox();
              const mascotRect = await mascot.boundingBox();
              const safeTop = 64;
              const safeBottom = 780 - panelRect.height - 8;
              const desired = mascotRect.y + (mascotRect.height - panelRect.height) / 2;
              const expected = Math.max(safeTop, Math.min(safeBottom, desired));
              const label = `${engine.name()} ${edge} windows=${windowCount} scale=${scale} width=${compactWidth} y=${requestedY}`;
              assert.ok(Math.abs(panelRect.y - expected) <= 1,
                `${label}: compact clamp mismatch ${panelRect.y} != ${expected}`);
              if (desired >= safeTop && desired <= safeBottom) {
                assert.ok(Math.abs(panelRect.y + panelRect.height / 2
                  - mascotRect.y - mascotRect.height / 2) <= 1,
                `${label}: unclamped centers differ`);
              } else {
                const boundary = desired < safeTop ? safeTop : safeBottom;
                assert.ok(Math.abs(panelRect.y - boundary) <= 1,
                  `${label}: compact panel did not stop at its safe boundary`);
              }
             }
            }
          }
        }
        assert.equal(await publish(page, call, base), true);
        await page.evaluate(edge => {
          const root = document.querySelector('.cti-hud');
          localStorage.setItem('cti-mascot-scale', '1');
          root.__ctiLayout.compact = {edge, y:180, width:270};
          root.__ctiApplyPosition();
        }, edge);
        await page.emulateMedia({reducedMotion:'no-preference'});

        const transition = await gauge.evaluate(node => {
          const style = getComputedStyle(node);
          return {property:style.transitionProperty, duration:style.transitionDuration};
        });
        assert.ok(transition.property.includes('opacity') && transition.property.includes('transform'));
        assert.notEqual(transition.duration, '0s');

        for (let round = 0; round < 3; round++) {
          await mascot.hover();
          await page.waitForTimeout(220);
          assert.equal(await root.getAttribute('data-revealed'), 'true');
          assert.equal(await root.getAttribute('data-collapsed'), 'true',
            `${engine.name()} ${edge}: round ${round} must reopen compact`);
          assert.equal(await gauge.evaluate(node => getComputedStyle(node).opacity), '0');
          await toggle.click();
          assert.equal(await root.getAttribute('data-collapsed'), 'false');
          await page.waitForTimeout(220);
          const expandedRect = await root.boundingBox();
          const expandedMascot = await mascot.boundingBox();
          const expandedBottom = Math.max(64,
            780 - Math.max(expandedRect.height, expandedMascot.height) - 8);
          const expandedY = Math.max(64, Math.min(expandedBottom, 180));
          assert.ok(Math.abs(expandedRect.y - expandedY) < 1,
            `${engine.name()} ${edge}: expanded mode changed its established clamp`);
          await page.mouse.move(550, 740);
          await page.waitForTimeout(760);
          assert.equal(await root.getAttribute('data-revealed'), 'false');
          assert.equal(await root.getAttribute('data-collapsed'), 'true',
            `${engine.name()} ${edge}: round ${round} auto-hide must restore compact`);
          assert.equal(await page.evaluate(() =>
            localStorage.getItem('codex-context-token-inspector-collapsed')), 'true');
          assert.equal(await gauge.evaluate(node => getComputedStyle(node).opacity), '1');
          assert.ok(Math.abs((await mascot.boundingBox()).y - 180) < 1,
            `${engine.name()} ${edge}: round ${round} moved mascot Y anchor`);
        }
        await page.screenshot({path:path.join(
          artifacts, `${engine.name()}-${edge}-auto-hidden-restored.png`)});

        await mascot.hover();
        await mascot.click();
        assert.equal(await root.getAttribute('data-dock-pinned'), 'true');
        await toggle.click();
        assert.equal(await root.getAttribute('data-collapsed'), 'false');
        await page.mouse.move(550, 740);
        await page.waitForTimeout(760);
        assert.equal(await root.getAttribute('data-revealed'), 'true');
        assert.equal(await root.getAttribute('data-collapsed'), 'false',
          'explicit pin must preserve the expanded panel');
        await toggle.press('Escape');
        assert.equal(await root.getAttribute('data-dock-pinned'), 'false');
        assert.equal(await root.getAttribute('data-revealed'), 'false');
        await mascot.hover();
        await page.waitForTimeout(220);
        await toggle.click();
        await page.mouse.move(550, 740);
        await page.waitForTimeout(760);

        await mascot.focus();
        assert.equal(await root.getAttribute('data-revealed'), 'true');
        await toggle.focus();
        await page.waitForTimeout(760);
        assert.equal(await root.getAttribute('data-revealed'), 'true',
          'moving keyboard focus into the panel must keep it open');
        await page.evaluate(() => document.activeElement.blur());
        await page.waitForTimeout(760);
        assert.equal(await root.getAttribute('data-revealed'), 'false');
        assert.equal(await root.getAttribute('data-collapsed'), 'true');

        await page.emulateMedia({reducedMotion:'reduce'});
        const reduced = await gauge.evaluate(node => getComputedStyle(node).transitionDuration);
        assert.equal(reduced.split(',').every(value => value.trim() === '0s'), true);
        await mascot.hover();
        assert.equal(await gauge.evaluate(node => getComputedStyle(node).opacity), '0');
        await page.screenshot({path:path.join(
          artifacts, `${engine.name()}-${edge}-compact-revealed-reduced-motion.png`)});
        await toggle.click();
        assert.equal(await root.getAttribute('data-collapsed'), 'false');
        assert.equal(await gauge.evaluate(node => getComputedStyle(node).opacity), '0');
        await page.screenshot({path:path.join(
          artifacts, `${engine.name()}-${edge}-expanded-reduced-motion.png`)});
        await page.evaluate(() => {
          const root = document.querySelector('.cti-hud');
          root.__ctiLayout.expanded = {x:320, y:170, width:330};
          root.__ctiApplyPosition();
        });
        assert.equal(await root.getAttribute('data-docked'), null);
        assert.equal(await root.getAttribute('data-collapsed'), 'false');
        await root.hover();
        await page.mouse.move(1000, 740);
        await page.waitForTimeout(760);
        assert.equal(await root.getAttribute('data-collapsed'), 'false',
          'a floating expanded panel must ignore dock auto-hide');
        assert.deepEqual(errors, []);
        await context.close();
        console.log(`${engine.name()} ${edge}: six skins, four scales, three auto-hide rounds, pin, keyboard and reduced motion passed`);
      }
    } finally {
      await browser.close();
    }
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
