const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium, webkit} = require('playwright');
const source = fs.readFileSync(path.join(__dirname, '../quota_monitor/panel_account_windows.js'), 'utf8');
(async () => {
 for (const engine of [chromium, webkit]) {
  const browser = await engine.launch();
  try {
   const page = await browser.newPage();
   await page.setContent('<main></main>');
   await page.evaluate(source => {
    window.uiLanguage = () => window.language;
    window.windowLabel = () => '<b>window</b>';
    window.quotaTone = value => value <= 20 ? 'low' : value <= 50 ? 'watch' : 'safe';
    window.toneLabel = tone => tone;
    (0, eval)(source);
   }, source);
   for (const language of ['zh', 'en']) {
    for (const [minutes, phrase] of [[0,language === 'zh' ? '等待刷新' : 'Awaiting refresh'],[1,language === 'zh' ? '1 分钟后' : '1 min'],[60,'1h 0m'],[1440,language === 'zh' ? '1 天 0h' : '1d 0h']]) {
     await page.evaluate(({language, minutes}) => {
      window.language = language;
      document.querySelector('main').innerHTML = accountWindowHTML([{remaining:80,duration:300,resetsAt:1000+minutes*60,paceDelta:3,projectedExhaustAt:3000}], false, 1000);
     }, {language, minutes});
     assert.ok((await page.locator('main').textContent()).includes(phrase));
     assert.equal(await page.locator('b').count(), 0);
     assert.ok((await page.locator('main').textContent()).includes('<b>window</b>'));
     assert.equal(await page.locator('[role=meter]').getAttribute('aria-valuenow'), '80');
     assert.equal(await page.locator('.cti-quota-window').getAttribute('data-tone'), 'safe');
     assert.ok((await page.locator('main').textContent()).includes(language === 'zh' ? '耗尽' : 'exhausted'));
    }
    await page.evaluate(language => {
     window.language = language;
     document.querySelector('main').innerHTML = accountWindowHTML([{remaining:0,paceDelta:-3},{remaining:100,paceDelta:0}], true, 1000);
    }, language);
    assert.equal(await page.locator('[role=meter]').count(), 2);
    assert.deepEqual(await page.locator('.cti-quota-window').evaluateAll(nodes => nodes.map(node => node.dataset.tone)), ['low','low']);
    assert.ok((await page.locator('main').textContent()).includes(language === 'zh' ? '慢于均匀进度' : 'Behind pace'));
    assert.ok((await page.locator('main').textContent()).includes(language === 'zh' ? '符合均匀进度' : 'On steady pace'));
    assert.equal(await page.evaluate(() => accountWindowHTML([], false, 1000)), '');
   }
   console.log(engine.name()+': window rows, countdown thresholds, forecast, blocked groups and literal labels passed');
  } finally { await browser.close(); }
 }
})().catch(error => { console.error(error); process.exitCode=1; });
