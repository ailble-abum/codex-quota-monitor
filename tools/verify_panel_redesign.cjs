// Synthetic-only visual and interaction regression; never connects to the installed monitor.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium, webkit} = require('playwright');
const [consumer, artifacts = '/tmp/quota-ui-20261005-evidence'] = process.argv.slice(2);
const source = fs.readFileSync(consumer, 'utf8');
const bridge = fs.readFileSync(path.join(__dirname,'../quota_monitor/page_bridge.js'),'utf8');
fs.mkdirSync(artifacts, {recursive:true});
const payload = () => ({activeThreadId:'synthetic', observedAt:Date.now()/1000, summaries:[],
  quota:{status:'live', updatedAt:Date.now()/1000, planType:'pro', windows:[{duration:10080, remaining:86, paceDelta:21, resetsAt:Date.now()/1000+390000}],
    usage:{dailyUsageBuckets:[{tokens:134200000}], summary:{lifetimeTokens:29900100000}}, resetCredits:{availableCount:2}},
  history:{samples:9073, spanSeconds:345600, minRemaining:0, peakContext:53, averageCachedShare:99, models:['gpt-6.1-sol'],
    weekly:{days:Array.from({length:7},(_,i)=>({date:`2026-10-0${i+1}`,samples:i*300,peakContext:53})),
      modelCounts:[{model:'gpt-6.1-sol',samples:3}], projectCounts:[{project:'配额监控',samples:3}]}}});
(async()=>{
for (const engine of [chromium, webkit]) {
 const browser=await engine.launch();
 try {
  for(const language of ['zh','en']) for(const colorScheme of ['light','dark']) {
   const page=await browser.newPage({viewport:{width:1000,height:850},colorScheme,locale:language==='zh'?'zh-CN':'en'});
   const errors=[]; page.on('pageerror',e=>errors.push(e.message));
   await page.route('**/*',route=>route.fulfill({contentType:'text/html',body:`<!doctype html><html><style>
    :root{color-scheme:light dark}body{background:Canvas;color:CanvasText}button{margin:8px;padding:12px;line-height:2}p{margin:1em 0}input{appearance:none}
   </style><body></body></html>`}));
   await page.goto('http://redesign.invalid/');
   await page.emulateMedia({reducedMotion:'reduce'});
   await page.evaluate(language=>{
    window.__quotaMonitorV2Thread='synthetic';
    localStorage.setItem('cti-language',language);
    localStorage.setItem('cti-layout-v2',JSON.stringify({expanded:{x:350,y:80},compact:{x:350,y:720}}));
    localStorage.setItem('cti-mascot-skin','tea');
   },language);
   const call=options=>page.evaluate(({bridge,options})=>(0,eval)(bridge)(options),{bridge,options});
   const base={expected:'http://redesign.invalid/',key:'synthetic'};
   await call({...base,action:'initialize',consumer:{source}});
   const root=page.locator('.cti-hud');
   const publish=(data=payload())=>call({...base,action:'publish',payload:data,panel:true});
   await publish();
   assert.equal(await page.locator('[data-history-disclosure]').evaluate(n=>n.open),false);
   assert.equal(await page.locator('.cti-account-breakdown').evaluate(n=>n.open),false);
   assert.ok((await root.boundingBox()).height<550,'overview should fit without a long ledger');
   const buttons=await page.locator('.cti-header-actions button').evaluateAll(nodes=>nodes.map(n=>{
     const b=n.getBoundingClientRect();return {w:b.width,h:b.height,cy:b.y+b.height/2};}));
   for(const b of buttons) {assert.equal(b.w,buttons[0].w);assert.equal(b.h,buttons[0].h);assert.equal(b.cy,buttons[0].cy);}
   const iconSizes=await page.locator('.cti-header-actions svg').evaluateAll(nodes=>nodes.map(n=>{const b=n.getBoundingClientRect();return[b.width,b.height];}));
   assert.deepEqual(iconSizes,[[16,16],[16,16]]);
   await root.screenshot({path:path.join(artifacts,`${engine.name()}-${language}-${colorScheme}-overview.png`)});
   await page.locator('.cti-account-breakdown > summary').click();
   await publish();
   assert.equal(await page.locator('.cti-account-breakdown').evaluate(n=>n.open),true,'quota refresh must preserve open details');
   await page.locator('.cti-account-breakdown > summary').click();
   await page.locator('[data-history-disclosure] > summary').click();
   assert.ok(await page.locator('[data-history]').isVisible());
   await publish();
   assert.equal(await page.locator('[data-history-disclosure]').evaluate(n=>n.open),true,'refresh preserves disclosure');
   await page.locator('[data-settings-toggle]').click();
   assert.equal(await page.locator('[data-overview]').isVisible(),false);
   assert.equal(await page.locator('[data-settings]').isVisible(),true);
   assert.equal(await page.locator('[data-companion-settings]').evaluate(n=>n.open),false);
   assert.ok(await page.locator('[data-edge-dock]').isVisible());
   assert.equal(await page.locator('[data-edge-dock]').evaluate(n=>getComputedStyle(n).appearance),'auto');
   assert.ok((await root.boundingBox()).height<650,'settings must start as a short grouped view');
   await root.screenshot({path:path.join(artifacts,`${engine.name()}-${language}-${colorScheme}-settings.png`)});
   for(const preset of ['mini','large','standard']) {
    await page.locator(`[data-layout-preset="${preset}"]`).click();
    assert.ok(await page.locator('[data-settings]').evaluate(n=>n.scrollWidth<=n.clientWidth+1),'settings must fit every panel size');
    const boxes=await page.locator('.cti-header-actions button').evaluateAll(nodes=>nodes.map(n=>{const b=n.getBoundingClientRect();return[b.width,b.height,b.y];}));
    assert.deepEqual(boxes[0],boxes[1]);assert.deepEqual(boxes[1],boxes[2]);
   }
   await page.locator('[data-companion-settings] > summary').click();
   await page.locator('[data-skins] > summary').click();
   await page.locator('[data-skin-choice="cat"]').click();
   await publish();
   assert.equal(await page.locator('[data-companion-settings]').evaluate(n=>n.open),true);
   await page.locator('[data-language]').selectOption(language==='zh'?'en':'zh');
   assert.equal(await page.locator('[data-overview]').isVisible(),false,'language change retains settings view');
   assert.equal(await page.locator('[data-companion-settings]').evaluate(n=>n.open),true);
   assert.equal(await page.locator('[data-skins]').evaluate(n=>n.open),true);
   await page.locator('[data-language]').selectOption(language);
   // Long unbroken values must remain readable inside the expanded history.
   const long=payload();long.history.models=['m'.repeat(128)];long.history.weekly.projectCounts=[{project:'p'.repeat(80),samples:3}];
   await publish(long);
   await page.locator('[data-settings-back]').click();
   assert.equal(await page.locator('[data-history-disclosure]').evaluate(n=>n.open),true);
   assert.ok(await page.locator('[data-history]').evaluate(n=>n.scrollWidth<=n.clientWidth+1));
   // Real drag from compact mode, followed by viewport clamping and round trips.
   await page.locator('[data-cti-toggle]').click();
   const title=await page.locator('[data-cti-title]').boundingBox();
   await page.mouse.move(title.x+10,title.y+title.height/2);await page.mouse.down();
   await page.mouse.move(title.x+10,735,{steps:5});await page.mouse.up();
   await page.waitForFunction(()=>performance.now()>(document.querySelector('.cti-hud').__ctiSuppressClickUntil||0));
   const before=await root.boundingBox();
   for(let i=0;i<3;i++) {
    await page.locator('[data-cti-toggle]').click();
    assert.ok((await root.boundingBox()).y<before.y-100,'expanded view must clamp above the saved bottom anchor');
    await page.locator('[data-settings-toggle]').click();
    await page.locator('[data-settings-back]').click();
    await publish();
    await page.locator('[data-cti-toggle]').click();
    const after=await root.boundingBox();
    assert.ok(Math.abs(after.y-before.y)<1,`bottom anchor drifted: ${before.y} -> ${after.y}`);
    assert.ok(Math.abs(after.x-before.x)<1,'horizontal anchor must also survive clamping');
   }
   const stored=await page.evaluate(()=>JSON.parse(localStorage.getItem('cti-layout-v2')));
   assert.ok(Math.abs(stored.compact.y-before.y)<1);
   // Restore the saved anchor after a temporarily smaller viewport.
   await page.setViewportSize({width:650,height:450});
   await page.locator('[data-cti-toggle]').click();await page.locator('[data-cti-toggle]').click();
   await page.setViewportSize({width:1000,height:850});
   await page.waitForFunction(y=>Math.abs(document.querySelector('.cti-hud').getBoundingClientRect().y-y)<1,before.y);
   assert.deepEqual(errors,[]);
   await page.close();
   console.log(`${engine.name()} ${language} ${colorScheme}: hierarchy, controls, disclosure state, host CSS, long text, bottom-anchor round trips passed`);
  }
 } finally {await browser.close();}
}
})().catch(e=>{console.error(e);process.exitCode=1;});
