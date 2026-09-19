const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium, webkit} = require('playwright');
const source = fs.readFileSync(path.join(__dirname, '../quota_monitor/panel_account_status.js'), 'utf8');
(async () => {
  for (const engine of [chromium, webkit]) {
    const browser = await engine.launch();
    try {
      const page = await browser.newPage();
      await page.setContent('<section><div data-freshness></div></section>');
      await page.evaluate(source => { window.uiLanguage = () => window.language; (0, eval)(source); }, source);
      for (const language of ['zh', 'en']) {
        const render = (quota, live, age) => page.evaluate(({quota, live, age, language}) => {
          window.language = language;
          const body = document.querySelector('section'), node = body.firstChild;
          renderAccountStatus(body, quota, live, age);
          const first = node.firstChild;
          renderAccountStatus(body, quota, live, age);
          return {text: node.textContent, children: node.children.length, stable: first === node.firstChild};
        }, {quota, live, age, language});
        let result = await render({planType: '<b>pro</b>'}, true, 9);
        assert.equal(result.children, 0); assert.equal(result.stable, true);
        assert.ok(result.text.includes('<b>pro</b>'));
        assert.ok(result.text.includes(language === 'zh' ? '刚刚更新' : 'just updated'));
        result = await render({planType: 'plus'}, true, 10);
        assert.ok(result.text.includes('Plus')); assert.ok(result.text.includes('10s'));
        result = await render({errorCode: 'timeout'}, false, null);
        assert.ok(result.text.includes(language === 'zh' ? '读取超时' : 'timed out'));
        result = await render({errorCode: '<img src=x>'}, false, null);
        assert.equal(result.children, 0); assert.ok(result.text.includes('<img src=x>'));
        result = await render({errorCode: {bad: 1}, planType: 12}, false, null);
        assert.equal(result.text.includes('[object'), false);
        assert.ok(result.text.includes(language === 'zh' ? '本地 Token 独立读取' : 'local tokens independent'));
      }
      console.log(engine.name() + ': bilingual account status, literal fields, known errors and unchanged nodes passed');
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
