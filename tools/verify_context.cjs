const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium, webkit} = require('playwright');
const source = ['panel_format.js', 'panel_context.js'].map(name => fs.readFileSync(path.join(__dirname, '../quota_monitor', name), 'utf8')).join('\n');
(async () => {
  for (const engine of [chromium, webkit]) {
    const browser = await engine.launch();
    try {
      const page = await browser.newPage();
      await page.setContent('<section><div data-context></div></section>');
      await page.evaluate(source => {
        window.unitMode = () => 'auto'; window.uiLanguage = () => window.language || 'zh';
        window.tr = () => 'No records';
        (0, eval)(source);
      }, source);
      for (const language of ['zh', 'en']) {
        for (const [input, value, tone] of [[-5,0,'safe'],[0,0,'safe'],[69.9,69.9,'safe'],[70,70,'watch'],[85,85,'low'],[120,100,'low'],[null,null,'unknown'],['50',null,'unknown'],[NaN,null,'unknown'],[Infinity,null,'unknown']]) {
          await page.evaluate(({input, language}) => {
            window.language = language;
            window.sample = {latest_context_percent: input, latest_context_tokens: 500, context_window: 1000};
            renderContext(document.querySelector('section'), window.sample);
          }, {input, language});
          const box = page.locator('[data-context]');
          assert.equal(await box.getAttribute('data-tone'), tone);
          assert.equal(await box.locator('[role=meter]').count(), value === null ? 0 : 1);
          if (value !== null) {
            assert.equal(await box.locator('[role=meter]').getAttribute('aria-valuenow'), String(value));
            assert.equal(await box.locator('[role=meter]').getAttribute('aria-label'), language === 'zh' ? '上下文占用' : 'Context used');
            assert.ok((await box.textContent()).includes('500 / 1K'));
          }
          assert.equal(await page.evaluate(() => {
            const box = document.querySelector('[data-context]'), first = box.firstChild;
            renderContext(document.querySelector('section'), window.sample);
            return box.firstChild === first;
          }), true);
        }
      }
      await page.evaluate(() => renderContext(document.querySelector('section'), null));
      assert.equal(await page.locator('[data-context]').textContent(), 'No records');
      assert.equal(await page.locator('[role=meter]').count(), 0);
      console.log(engine.name() + ': context boundaries, invalid values, languages, unchanged nodes and missing records passed');
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
