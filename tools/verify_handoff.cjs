const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium, webkit} = require('playwright');
const source = fs.readFileSync(path.join(__dirname, '../quota_monitor/panel_handoff.js'), 'utf8');
(async () => { for (const engine of [chromium, webkit]) {
 const browser = await engine.launch();
 try {
  const page = await browser.newPage();
  await page.setContent('<button data-handoff>Copy</button>');
  await page.evaluate(source => {
   window.uiLanguage = () => window.language || 'zh';
   Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{writeText: text => {
    window.copied = text; window.calls = (window.calls || 0) + 1;
    return new Promise((resolve, reject) => {window.finishCopy = resolve; window.failCopy = reject;});
   }}});
   (0,eval)(source);
  }, source);
  await page.evaluate(() => {
   const button = document.querySelector('button');
   window.pending = copyHandoff(button);
   copyHandoff(button);
  });
  assert.equal(await page.evaluate(() => window.calls), 1);
  assert.equal(await page.locator('button').isDisabled(), true);
  assert.ok((await page.evaluate(() => window.copied)).includes('验证'));
  await page.evaluate(async () => {finishCopy(); await pending;});
  assert.equal(await page.locator('button').isDisabled(), false);
  assert.ok((await page.locator('button').textContent()).includes('已复制'));
  await page.evaluate(async () => {window.language='en';window.pending=copyHandoff(document.querySelector('button'));failCopy(Error('denied'));await pending;});
  assert.ok((await page.locator('button').textContent()).includes('Copy failed'));
  assert.ok((await page.evaluate(() => window.copied)).includes('verification'));
  await page.evaluate(() => {
   window.oldButton=document.querySelector('button');
   window.pending=copyHandoff(oldButton);
   oldButton.replaceWith(Object.assign(document.createElement('button'),{textContent:'Replacement'}));
  });
  await page.evaluate(async () => {finishCopy();await pending;});
  assert.equal(await page.locator('button').textContent(), 'Replacement');
  assert.equal(await page.evaluate(() => oldButton.textContent), 'Copy failed; request a handoff in this task.');
  await page.evaluate(async () => {Object.defineProperty(navigator,'clipboard',{value:undefined}); await copyHandoff(document.querySelector('button'));});
  assert.ok((await page.locator('button').textContent()).includes('Copy failed'));
  console.log(engine.name()+': bilingual copy, failure, duplicate prevention and detached completion passed');
 } finally {await browser.close();}
}})().catch(error=>{console.error(error);process.exitCode=1;});
