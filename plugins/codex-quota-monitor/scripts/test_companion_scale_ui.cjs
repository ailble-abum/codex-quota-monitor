// Run with Playwright available in NODE_PATH; all data stays in an isolated browser.
const { chromium, webkit } = require('playwright');
const { execFileSync } = require('node:child_process');
const assert = require('node:assert/strict');
const path = require('node:path');
const script = execFileSync(process.env.PYTHON || 'python3', ['-c', 'from context_token_injector import INJECTION_SCRIPT; print(INJECTION_SCRIPT)'], { cwd: __dirname, maxBuffer: 10 * 1024 * 1024, encoding: 'utf8' });
const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1, `${actual} != ${expected}`);
(async () => {
  for (const engine of [chromium, webkit]) {
    const browser = await engine.launch();
    try {
      // Measure layout without the post-drag landing animation scaling the image.
      // Animated feedback is covered separately by verify_companion_ui.cjs.
      const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, locale: 'zh-CN', reducedMotion: 'reduce' });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('http://companion.test/**', route => route.fulfill({ contentType: 'text/html', body: '<html lang="zh-CN"><style>:root{color-scheme:light dark}body{background:Canvas;color:CanvasText}</style><body></body></html>' }));
      await page.goto('http://companion.test/');
      await page.evaluate(() => {
        localStorage.setItem('cti-language', 'zh');
        localStorage.setItem('cti-layout-v2', JSON.stringify({ expanded: { edge: 'right', y: 100 } }));
      });
      const inject = () => page.evaluate(`(${script})({summaries:[],quota:{status:'live',updatedAt:Date.now()/1000,windows:[{remaining:70,label:'Daily'}]}})`);
      await inject();
      const mascot = page.locator('.cti-edge-mascot');
      await mascot.locator('img').evaluate(img => img.decode());
      const dimensions = () => page.evaluate(async () => {
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        const m = document.querySelector('.cti-edge-mascot');
        const rect = node => { const r = node.getBoundingClientRect(); return { height:r.height,width:r.width,top:r.top,bottom:r.bottom,left:r.left,right:r.right }; };
        return { mascot:rect(m), image:rect(m.querySelector('img')), gauge:rect(m.querySelector('[data-gauge]')), ring:rect(m.querySelector('[data-context-ring]')), panel:rect(document.querySelector('.cti-hud')) };
      });
      let small = await dimensions(); near(small.image.height, 48); near(small.mascot.top, 100); near(small.mascot.right, 1280);
      await page.setViewportSize({ width: 2560, height: 1440 });
      let big = await dimensions(); near(big.image.height, 72); near(big.mascot.top, 100); near(big.mascot.right, 2560);
      near(big.gauge.width, small.gauge.width * 1.5); near(big.ring.width, small.ring.width * 1.5);
      // Open real settings and exercise the actual input listener, independent of panel size.
      await mascot.focus();
      await page.locator('[data-settings-toggle]').click();
      const slider = page.locator('[data-mascot-scale]');
      const setScale = value => slider.evaluate((el,value) => { el.value=value; el.focus(); el.dispatchEvent(new Event('input',{bubbles:true})); }, value);
      await setScale('200');
      await page.mouse.move(500, 500);
      await page.waitForTimeout(200);
      near((await dimensions()).image.height, 96);
      assert.equal(await page.evaluate(() => localStorage.getItem('cti-mascot-scale')), '2');
      await page.setViewportSize({ width: 1280, height: 800 });
      near((await dimensions()).image.height, 96);
      await page.reload(); await inject(); await mascot.locator('img').evaluate(img => img.decode());
      near((await dimensions()).image.height, 96);
      // All skins remain flush to both walls; the actual pointer drag stays in bounds.
      for (const edge of ['left', 'right']) for (const skin of ['cat','candy','corgi','mint','frost','tea']) {
        await page.evaluate(({edge,skin}) => {
          localStorage.setItem('cti-mascot-skin', skin);
          const root = document.querySelector('.cti-hud'); root.__ctiLayout = { expanded: { edge, y: 100 } };
          window.dispatchEvent(new Event('resize'));
        }, {edge,skin});
        await mascot.locator('img').evaluate(img => img.decode());
        const d = await dimensions(); near(d.image.height, 96); near(d.mascot[edge], edge === 'left' ? 0 : 1280);
      }
      let box = await mascot.boundingBox();
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down(); await page.mouse.move(1270, 795, { steps: 5 }); await page.mouse.up();
      await page.mouse.move(500,500); await page.waitForTimeout(200);
      assert.ok((await dimensions()).mascot.bottom <= 800);
      await mascot.focus();
      await page.locator('[data-settings-toggle]').click();
      await page.locator('[data-mascot-scale-auto]').click();
      near((await dimensions()).image.height, 48);
      assert.equal(await page.evaluate(() => localStorage.getItem('cti-mascot-scale')), null);
      await setScale('75'); near((await dimensions()).image.height, 36);
      await slider.focus(); await page.keyboard.press('ArrowRight');
      assert.equal(await page.evaluate(() => localStorage.getItem('cti-mascot-scale')), '0.76');
      for (const colorScheme of ['light','dark']) {
        await page.emulateMedia({ colorScheme });
        await setScale('150');
        await page.screenshot({ path: path.join(process.env.ARTIFACT_DIR || '/tmp', `companion-scale-${engine.name()}-${colorScheme}.png`) });
      }
      assert.deepEqual(errors, []);
      console.log(`${engine.name()}: auto/manual, persistence, 6 skins × 2 edges, drag, reset, keyboard, light/dark passed`);
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
