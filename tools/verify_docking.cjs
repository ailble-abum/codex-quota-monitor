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
     localStorage.setItem('cti-mascot-skin','tea');
     localStorage.setItem('cti-layout-v2',JSON.stringify({
       expanded:{edge,y:80}, compact:{edge:edge === 'left' ? 'right' : 'left',y:360}
     }));
    },edge);
    const call = options => page.evaluate(({bridge,options}) => (0,eval)(bridge)(options),{bridge,options});
    const base={expected:'http://dock.invalid/',key:'one'};
    assert.equal(await call({...base,action:'initialize',consumer:{source}}),'ready');
    const root=page.locator('.cti-hud'), mascot=page.locator('#codex-context-token-inspector-mascot');
    const gauge=mascot.locator('[data-gauge]'), art=mascot.locator('.cti-mascot-art');
    assert.equal(await root.getAttribute('data-docked'),'true');
    assert.equal(await root.getAttribute('data-revealed'),'false');
    // Keyboard focus is the supported reveal path; click pins the panel open.
    await mascot.focus();
    assert.equal(await root.getAttribute('data-revealed'),'true');
    await mascot.click();
    assert.equal(await root.getAttribute('data-dock-pinned'),'true');
    const payload={activeThreadId:'one',selectedThreadId:'one',observedAt:Date.now()/1000,
      summaries:[{thread_id:'one',latest_context_percent:50,latest_context_tokens:500,context_window:1000}],
      quota:{status:'live',updatedAt:Date.now()/1000,windows:[{remaining:19,duration:10080}]},
      history:{samples:104,spanSeconds:172800,peakContext:91,averageCachedShare:94,
        models:['gpt-6-astra','gpt-5.6-sol'],weekly:{days:[
          {date:'2026-09-20',samples:0},{date:'2026-09-21',samples:0},
          {date:'2026-09-22',samples:0},{date:'2026-09-23',samples:0},
          {date:'2026-09-24',samples:4,peakContext:54},{date:'2026-09-25',samples:0},
          {date:'2026-09-26',samples:100,peakContext:91}],
        modelCounts:[{model:'gpt-6-astra',samples:102},{model:'gpt-5.6-sol',samples:1}],
        projectCounts:[{project:'《我的绝对理性系统》',samples:94},{project:'Openclaw',samples:8},{project:'Comfyui项目',samples:1}]}}};
    await call({...base,action:'publish',payload,panel:true});
    for (const scale of [.75,1,1.5,2]) {
     await page.evaluate(scale => {
     localStorage.setItem('cti-mascot-scale',String(scale));
     document.querySelector('.cti-hud').__ctiApplyPosition();
     },scale);
     await page.waitForTimeout(220);
     const panelRect=await root.boundingBox(), mascotRect=await mascot.boundingBox();
     const gaugeRect=await gauge.boundingBox(), artRect=await art.boundingBox();
     assert.ok(Math.abs(mascotRect.y-80)<1,
       `${engine.name()} ${edge} ${scale}: mascot must retain its stored anchor`);
     assert.ok(panelRect.y>=63 && panelRect.y+panelRect.height<=1193,
       `${engine.name()} ${edge} ${scale}: panel must clamp independently into the viewport`);
     assert.ok(mascotRect.x>=-1 && mascotRect.x+mascotRect.width<=1281,
       `${engine.name()} ${edge} ${scale}: mascot must stay inside the viewport`);
     assert.ok(panelRect.x>=-1 && panelRect.x+panelRect.width<=1281,
       `${engine.name()} ${edge} ${scale}: panel must stay inside the viewport`);
     const visibleLeft=artRect.x+artRect.width*86/320;
     const visibleRight=artRect.x+artRect.width;
     if(edge==='right') {
      assert.ok(Math.abs(visibleLeft-(gaugeRect.x+gaugeRect.width)-4*scale)<.35,
        `${engine.name()} right ${scale}: gauge must keep space from the tea alpha bounds`);
      assert.ok(panelRect.x+panelRect.width<=gaugeRect.x-2,
        `${engine.name()} right ${scale}: panel must not cover the gauge`);
     } else {
      assert.ok(Math.abs(gaugeRect.x-visibleRight-4*scale)<.35,
        `${engine.name()} left ${scale}: gauge must keep space from the tea alpha bounds`);
      assert.ok(gaugeRect.x+gaugeRect.width<=panelRect.x-2,
        `${engine.name()} left ${scale}: panel must not cover the gauge`);
     }
     assert.equal(await gauge.evaluate(node=>getComputedStyle(node).opacity),'0',
       `${engine.name()} ${edge} ${scale}: revealed panel must retract the gauge`);
    }
    await page.evaluate(() => {
     localStorage.removeItem('cti-mascot-scale');
     document.querySelector('.cti-hud').__ctiApplyPosition();
    });
    await page.evaluate(()=>{
     window.collapseErrors=[];window.addEventListener('error',event=>collapseErrors.push(event.message));
     window.collapseSetItem=Storage.prototype.setItem;
     Storage.prototype.setItem=function(key,value){if(key==='codex-context-token-inspector-collapsed')throw Error('full');return collapseSetItem.call(this,key,value);};
    });
    const toggle=page.locator('[data-cti-toggle]');
    const dockBefore=await mascot.boundingBox();
    await toggle.click();
    assert.equal(await root.getAttribute('data-collapsed'),'true');
    await page.waitForTimeout(220);
    const compactRect=await mascot.boundingBox();
    assert.equal(await root.getAttribute('data-dock-edge'),edge);
    assert.ok(Math.abs(compactRect.y-dockBefore.y)<1, 'collapse must retain the current dock anchor');
    await toggle.click();
    assert.equal(await root.getAttribute('data-collapsed'),'false');
    await page.waitForTimeout(220);
    const expandedRect=await mascot.boundingBox();
    assert.equal(await root.getAttribute('data-dock-edge'),edge);
    assert.ok(Math.abs(expandedRect.y-dockBefore.y)<1, 'expand must retain the current dock anchor');
    assert.equal(await root.getAttribute('data-revealed'),'true', 'pinned dock must stay revealed after mode changes');
    assert.deepEqual(await page.evaluate(()=>collapseErrors),[]);
    await page.evaluate(()=>{Storage.prototype.setItem=collapseSetItem;});
    await page.setViewportSize({width:900,height:700});
    await page.evaluate(() => {
     const node=document.querySelector('.cti-hud');
     node.__ctiLayout.expanded={...(node.__ctiLayout.expanded || {}),y:360};
     node.__ctiLayout.compact={...(node.__ctiLayout.compact || {}),y:360};
     node.__ctiApplyPosition();
    });
    await page.locator('[data-settings-toggle]').click();
    // A real click waited for the post-resize position/transition to settle.
    const rect=await root.boundingBox();
    assert.ok(rect.x>=0 && rect.y>=0 && rect.x+rect.width<=901 && rect.y+rect.height<=701, JSON.stringify(rect));
    const longMetrics=await root.evaluate(node=>({clientHeight:node.clientHeight,scrollHeight:node.scrollHeight}));
    assert.ok(longMetrics.scrollHeight>longMetrics.clientHeight,
      `${engine.name()} ${edge}: the real seven-day panel must scroll internally`);
    assert.ok(Math.abs((await mascot.boundingBox()).y-360)<1,
      `${engine.name()} ${edge}: long panel clamp must not move mascot anchor`);
    const lastSetting=page.locator('[data-position-reset]');
    await lastSetting.scrollIntoViewIfNeeded();
    const settingRect=await lastSetting.boundingBox(), scrollerRect=await root.boundingBox();
    assert.ok(settingRect.x>=scrollerRect.x && settingRect.x+settingRect.width<=scrollerRect.x+scrollerRect.width,
      'the last setting must remain horizontally reachable');
    assert.ok(settingRect.y>=scrollerRect.y && settingRect.y+settingRect.height<=scrollerRect.y+scrollerRect.height,
      'the last setting must remain vertically reachable after scrolling');
    await page.locator('[data-settings-toggle]').click();
    // Repeated mode changes must keep the mascot at the user's anchor while the
    // long panel independently moves upward to remain usable.
    for(let round=0;round<3;round++) {
     await toggle.click();
     await page.waitForTimeout(220);
     assert.equal(await root.getAttribute('data-collapsed'),'true');
     assert.ok(Math.abs((await mascot.boundingBox()).y-360)<1,
       `${engine.name()} ${edge}: collapse ${round} must retain mascot anchor`);
     await toggle.click();
     await page.waitForTimeout(220);
     assert.equal(await root.getAttribute('data-collapsed'),'false');
     const longRect=await root.boundingBox();
     assert.ok(longRect.y+longRect.height<=693, 'expanded panel must be clamped into the viewport');
     assert.ok(Math.abs((await mascot.boundingBox()).y-360)<1,
       `${engine.name()} ${edge}: expand ${round} must retain mascot anchor`);
    }
    await call({...base,action:'publish',payload,panel:true});
    await page.waitForTimeout(220);
    assert.ok(Math.abs((await mascot.boundingBox()).y-360)<1, 'data refresh must not move mascot anchor');
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
    const preview=page.locator('.cti-size-preview-art');
    assert.equal(await preview.evaluate(node=>node.complete && node.naturalWidth>0),true);
    assert.ok(Math.abs((await preview.boundingBox()).width-96)<2, 'preview should show the on-screen width');
    await page.locator('[data-skins] summary').click();
    const alphaBounds={candy:[23,294],cat:[0,320],corgi:[0,320],frost:[66,297],mint:[101,317],tea:[86,320]};
    for(const [skin,[alphaLeft,alphaRight]] of Object.entries(alphaBounds)) {
     await page.locator(`[data-skin-choice="${skin}"]`).click();
     const gaugeRect=await gauge.boundingBox(), artRect=await art.boundingBox(), panelRect=await root.boundingBox();
     const boundary=edge==='right'
       ? artRect.x+artRect.width*alphaLeft/320
       : artRect.x+artRect.width*alphaRight/320;
     const gaugeBoundary=edge==='right' ? gaugeRect.x+gaugeRect.width : gaugeRect.x;
     const scale=artRect.width/48;
     const gap=edge==='right' ? boundary-gaugeBoundary : gaugeBoundary-boundary;
     assert.ok(Math.abs(gap-4*scale)<.35,
       `${engine.name()} ${edge} ${skin}: gauge must keep space from the stable expression alpha bounds`);
     if(edge==='right') assert.ok(panelRect.x+panelRect.width<=gaugeRect.x-2,
       `${engine.name()} right ${skin}: panel must not cover the gauge`);
     else assert.ok(gaugeRect.x+gaugeRect.width<=panelRect.x-2,
       `${engine.name()} left ${skin}: panel must not cover the gauge`);
    }
    const previewSource=await preview.getAttribute('src');
    await page.locator('[data-skin-choice="corgi"]').click();
    assert.equal(await preview.evaluate((node,previous)=>node.src!==previous,previewSource),true);
    await page.locator('[data-skin-choice="cat"]').click();
    await page.locator('[data-skins] summary').click();
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
