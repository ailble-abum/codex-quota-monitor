const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium,webkit}=require('playwright');
const source=fs.readFileSync(path.join(__dirname,'../quota_monitor/panel_diagnostics.js'),'utf8');
(async()=>{for(const engine of [chromium,webkit]){const browser=await engine.launch();try{
 const page=await browser.newPage();await page.setContent('<main><div data-build></div><div data-update></div><div data-dom></div></main>');
 await page.evaluate(source=>{window.uiLanguage=()=>window.language;(0,eval)(source);},source);
 const render=(payload,language='zh')=>page.evaluate(({payload,language})=>{window.language=language;renderDiagnostics(document.querySelector('main'),payload);},{payload,language});
 for(const language of ['zh','en']){
  await render({},language);assert.ok((await page.locator('[data-dom]').textContent()).includes(language==='zh'?'未提供':'not provided'));
  await render({build:{pluginVersion:'<img src=x>',runtimeVersion:NaN,installedAt:Infinity},update:{status:'update_available',latestSemver:'<b>2</b>',url:'https://example.test/one'}},language);
  assert.equal(await page.locator('img,b').count(),0);assert.ok((await page.locator('[data-build]').textContent()).includes('<img src=x>'));
  assert.equal(await page.locator('[data-update] a').getAttribute('href'),'https://example.test/one');
  await render({update:{status:'update_available',latestSemver:'<b>2</b>',url:'https://example.test/two'}},language);
  assert.equal(await page.locator('[data-update] a').getAttribute('href'),'https://example.test/two');
  assert.equal(await page.locator('[data-update] a').getAttribute('rel'),'noopener noreferrer');
  for(const url of ['javascript:alert(1)','file:///tmp/test','http://example.test/','/relative','https://user:pass@example.test/']){
   await render({update:{status:'update_available',latestSemver:'2',url}},language);assert.equal(await page.locator('[data-update] a').count(),0);
  }
  await render({update:{status:'up_to_date'}},language);assert.ok((await page.locator('[data-update]').textContent()).includes(language==='zh'?'最新':'Up to date'));
  await render({update:{status:'error'},dom:{sidebarRows:0,activeRow:false,conversationId:false}},language);
  assert.equal(await page.locator('[data-update]').textContent(),language==='zh'?'检测更新':'Check for updates');assert.ok((await page.locator('[data-dom]').textContent()).includes(language==='zh'?'可能已更新':'may have changed'));
  await page.evaluate(()=>{window.previous=document.querySelector('[data-dom]').firstChild;});
  await render({update:{status:'error'},dom:{sidebarRows:0,activeRow:false,conversationId:false}},language);
  assert.equal(await page.evaluate(()=>window.previous===document.querySelector('[data-dom]').firstChild),true);
 }
 console.log(engine.name()+': literal metadata, missing diagnostics, updated HTTPS links and status clearing passed');
}finally{await browser.close();}}})().catch(error=>{console.error(error);process.exitCode=1;});
