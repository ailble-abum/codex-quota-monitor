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
    await page.evaluate(()=>{
     window.collapseErrors=[];window.addEventListener('error',event=>collapseErrors.push(event.message));
     window.collapseSetItem=Storage.prototype.setItem;
     Storage.prototype.setItem=function(key,value){if(key==='codex-context-token-inspector-collapsed')throw Error('full');return collapseSetItem.call(this,key,value);};
    });
    const toggle=page.locator('[data-cti-toggle]');
    await toggle.click();
    assert.equal(await root.getAttribute('data-collapsed'),'true');
    await toggle.click();
    assert.equal(await root.getAttribute('data-collapsed'),'false');
    assert.equal(await root.getAttribute('data-revealed'),'true', 'pinned dock must stay revealed after mode changes');
    assert.deepEqual(await page.evaluate(()=>collapseErrors),[]);
    await page.evaluate(()=>{Storage.prototype.setItem=collapseSetItem;});
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
    await page.locator('[data-settings-toggle]').click();
    await page.evaluate(() => {
     localStorage.setItem('cti-mascot-scale','1.25');
     window.scaleSetItem=Storage.prototype.setItem;window.scaleRemoveItem=Storage.prototype.removeItem;
     Storage.prototype.setItem=function(key,value){if(key==='cti-mascot-scale')throw Error('full');return scaleSetItem.call(this,key,value);};
     Storage.prototype.removeItem=function(key){if(key==='cti-mascot-scale')throw Error('denied');return scaleRemoveItem.call(this,key);};
    });
    await call({...base,action:'publish',payload,panel:true});
    const manualWidth=(await mascot.boundingBox()).width;
    const slider=page.locator('[data-mascot-scale]');
    await slider.focus();await page.keyboard.press('End');
    assert.equal(await mascot.evaluate(node=>node.style.getPropertyValue('--cti-mascot-scale')),'2');
    assert.equal(await page.locator('[data-mascot-scale-value]').textContent(),'200%');
    assert.ok((await mascot.boundingBox()).width > manualWidth);
    await page.waitForFunction(()=>{const node=document.querySelector('.cti-hud'),rect=node.getBoundingClientRect();return Math.abs(rect.left-parseFloat(node.style.left))<1 && Math.abs(rect.top-parseFloat(node.style.top))<1;});
    if(process.argv[3]) {
     for(const colorScheme of ['light','dark']) {
      await page.emulateMedia({colorScheme});
      await page.screenshot({path:path.join(process.argv[3],`${engine.name()}-${edge}-scale-${colorScheme}.png`)});
     }
    }

    assert.equal(await page.evaluate(()=>localStorage.getItem('cti-mascot-scale')),'1.25');
    await page.locator('[data-mascot-scale-auto]').click();
    assert.equal(await mascot.evaluate(node=>node.style.getPropertyValue('--cti-mascot-scale')),'1');
    assert.equal(await page.locator('[data-mascot-scale-auto]').getAttribute('aria-pressed'),'true');
    await call({...base,action:'publish',payload,panel:true});
    assert.equal(await slider.inputValue(),'100');
    await page.evaluate(()=>{Storage.prototype.setItem=scaleSetItem;Storage.prototype.removeItem=scaleRemoveItem;});
    await slider.focus();await page.keyboard.press('Home');
    assert.equal(await mascot.evaluate(node=>node.style.getPropertyValue('--cti-mascot-scale')),'0.75');
    assert.equal(await page.evaluate(()=>localStorage.getItem('cti-mascot-scale')),'0.75');
    await page.locator('[data-mascot-scale-auto]').click();
    assert.equal(await page.evaluate(()=>localStorage.getItem('cti-mascot-scale')),null);
    await page.evaluate(() => {
     localStorage.setItem('codex-context-token-inspector-position',JSON.stringify({left:500,top:200}));
     window.removalAttempts=[];window.resetErrors=[];
     window.addEventListener('error',event=>resetErrors.push(event.message));
     window.originalRemoveItem=Storage.prototype.removeItem;
     Storage.prototype.removeItem=function(key){
      if(['codex-context-token-inspector-position','cti-layout-v2'].includes(key)){removalAttempts.push(key);throw Error('denied');}
      return originalRemoveItem.call(this,key);
     };
    });
    await page.locator('[data-position-reset]').click();
    assert.equal(await root.getAttribute('data-docked'),null);
    assert.equal(await root.getAttribute('data-dock-pinned'),null);
    assert.equal(await root.getAttribute('data-revealed'),null);
    assert.deepEqual(await page.evaluate(()=>removalAttempts),['codex-context-token-inspector-position','cti-layout-v2']);
    assert.deepEqual(await root.evaluate(node=>node.__ctiLayout),{});
    assert.equal(await mascot.getAttribute('data-visible'),'false');
    await page.waitForFunction(()=>Math.abs(document.querySelector('.cti-hud').getBoundingClientRect().left-14)<1);
    const resetRect=await root.boundingBox();
    assert.ok(resetRect.x>=0 && resetRect.x+resetRect.width<=901 && resetRect.y>=0 && resetRect.y+resetRect.height<=701);
    await call({...base,action:'publish',payload,panel:true});
    assert.equal(await root.getAttribute('data-docked'),null);
    if(process.argv[3]) {
     for(const colorScheme of ['light','dark']) {
      await page.emulateMedia({colorScheme});
      await page.screenshot({path:path.join(process.argv[3],`${engine.name()}-${edge}-reset-${colorScheme}.png`)});
     }
    }
    await page.evaluate(()=>{Storage.prototype.removeItem=originalRemoveItem;});
    await page.locator('[data-position-reset]').click();
    assert.deepEqual(await page.evaluate(()=>['codex-context-token-inspector-position','cti-layout-v2'].map(key=>localStorage.getItem(key))),[null,null]);
    assert.deepEqual(await page.evaluate(()=>resetErrors),[]);
    await page.close();
    console.log(engine.name()+' '+edge+': restore, reveal, pin, resize, reset with failed deletes and recovery passed');
   }
  } finally {await browser.close();}
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
