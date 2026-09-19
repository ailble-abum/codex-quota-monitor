// Exercise retained docking through visible controls, never by forcing panel clicks.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium, webkit} = require('playwright');
(async () => {
 const source = fs.readFileSync(process.argv[2], 'utf8');
 const bridge = fs.readFileSync(path.join(__dirname, '../quota_monitor/page_bridge.js'), 'utf8');
 for (const engine of [chromium, webkit]) {
  const browser = await engine.launch();
  try {
   for (const edge of ['left','right']) {
    const page = await browser.newPage({viewport:{width:1280,height:1200}});
    await page.route('**/*', route => route.fulfill({contentType:'text/html',body:'<html><body></body></html>'}));
    await page.goto('http://dock.invalid/');
    await page.evaluate(edge => {
     window.__quotaMonitorV2Thread = 'one';
     localStorage.setItem('cti-language','zh');
     localStorage.setItem('cti-layout-v2',JSON.stringify({expanded:{edge,y:80}}));
    },edge);
    const call = options => page.evaluate(({bridge,options}) => (0,eval)(bridge)(options),{bridge,options});
    const base={expected:'http://dock.invalid/',key:'one'};
    assert.equal(await call({...base,action:'initialize',consumer:{source}}),'ready');
    const root=page.locator('.cti-hud'), mascot=page.locator('#codex-context-token-inspector-mascot');
    assert.equal(await root.getAttribute('data-docked'),'true');
    assert.equal(await root.getAttribute('data-revealed'),'false');
    // Keyboard focus is the supported reveal path; click pins the panel open.
    await mascot.focus();
    assert.equal(await root.getAttribute('data-revealed'),'true');
    await mascot.click();
    assert.equal(await root.getAttribute('data-dock-pinned'),'true');
    const payload={activeThreadId:'one',selectedThreadId:'one',observedAt:Date.now()/1000,
      summaries:[{thread_id:'one',latest_context_percent:50,latest_context_tokens:500,context_window:1000}],
      quota:{status:'live',updatedAt:Date.now()/1000,windows:[{remaining:10,duration:300},{remaining:90,duration:10080}]}};
    await call({...base,action:'publish',payload,panel:true});
    const toggle=page.locator('[data-cti-toggle]');
    await toggle.click();
    assert.equal(await root.getAttribute('data-collapsed'),'true');
    await toggle.click();
    assert.equal(await root.getAttribute('data-collapsed'),'false');
    assert.equal(await root.getAttribute('data-revealed'),'true', 'pinned dock must stay revealed after mode changes');
    await page.setViewportSize({width:900,height:700});
    await page.locator('[data-settings-toggle]').click();
    // A real click waited for the post-resize position/transition to settle.
    const rect=await root.boundingBox();
    assert.ok(rect.x>=0 && rect.y>=0 && rect.x+rect.width<=901 && rect.y+rect.height<=701, JSON.stringify(rect));
    await page.locator('[data-settings-toggle]').click();
    if(process.argv[3]) {
     fs.mkdirSync(process.argv[3],{recursive:true});
     await page.evaluate(()=>document.documentElement.style.colorScheme='light dark');
     for(const colorScheme of ['light','dark']) {
      await page.emulateMedia({colorScheme});
      await page.screenshot({path:path.join(process.argv[3],`${engine.name()}-${edge}-${colorScheme}.png`)});
     }
    }
    await page.close();
    console.log(engine.name()+' '+edge+': restore, focus reveal, pin, growth, toggle and viewport shrink passed');
   }
  } finally {await browser.close();}
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
