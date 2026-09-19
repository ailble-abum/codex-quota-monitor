const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium, webkit} = require('playwright');
const source = ['panel_format.js', 'panel_health.js'].map(name => fs.readFileSync(path.join(__dirname, '../quota_monitor', name), 'utf8')).join('\n');
(async () => {
  for (const engine of [chromium, webkit]) {
    const browser = await engine.launch();
    try {
      const page = await browser.newPage();
      await page.setContent('<section><div data-health></div></section>');
      await page.evaluate(source => {
        window.unitMode = () => 'auto'; window.uiLanguage = () => window.language;
        (0, eval)(source);
      }, source);
      const render = (health, language = 'zh') => page.evaluate(({health, language}) => {
        window.language = language; renderHealth(document.querySelector('section'), health);
        const box = document.querySelector('[data-health]');
        const first = box.firstChild;
        renderHealth(document.querySelector('section'), health);
        return {text: box.textContent, title: box.title, warning: box.dataset.warning,
          stable: first === box.firstChild, bold: box.querySelectorAll('strong').length, injected: box.querySelectorAll('img,b').length};
      }, {health, language});
      for (const language of ['zh', 'en']) {
        let result = await render({count: 2, after: 500, afterPercent: 50, recommendHandoff: true, reason: 'baseline'}, language);
        assert.equal(result.warning, 'true'); assert.equal(result.bold, 1); assert.equal(result.stable, true);
        assert.ok(result.text.includes('500 (50.0%)')); assert.ok(result.title.includes('40%'));
        result = await render({count: 1, recommendHandoff: true, reason: 'frequency'}, language);
        assert.ok(result.title.includes('5'));
        result = await render({count: 1, recommendHandoff: true, reason: 'unknown'}, language);
        assert.ok(result.title.includes(language === 'zh' ? '依据未提供' : 'basis unavailable'));
        result = await render({count: 1, after: null, recommendHandoff: 'true'}, language);
        assert.equal(result.warning, 'false'); assert.equal(result.bold, 0);
        assert.ok(result.text.includes(language === 'zh' ? '等待后续请求' : 'Awaiting next request'));
        for (const count of ['<b>5</b>', -1, 1.2, Infinity, NaN]) {
          result = await render({count, recommendHandoff: true}, language);
          assert.equal(result.warning, 'false'); assert.equal(result.injected, 0);
          assert.ok(result.text.includes(language === 'zh' ? '暂不可用' : 'unavailable'));
        }
        result = await render({count: 1, after: -1, afterPercent: Infinity}, language);
        assert.ok(result.text.includes(language === 'zh' ? '暂不可用' : 'unavailable'));
        result = await render(null, language);
        assert.equal(result.warning, 'false'); assert.equal(result.bold, 0);
        assert.ok(result.text.includes(language === 'zh' ? '尚未观察' : 'No observed'));
      }
      console.log(engine.name() + ': health values, invalid input, strict warnings, bilingual text and unchanged nodes passed');
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
