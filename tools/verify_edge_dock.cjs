const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium,webkit}=require('playwright');
(async()=>{for(const engine of [chromium,webkit]){const browser=await engine.launch();try{for(const edge of ['left','right']){
 const page=await browser.newPage({viewport:{width:1000,height:900}});
 await page.route('**/*',r=>r.fulfill({contentType:'text/html',body:'<html><body></body></html>'}));await page.goto('http://edge.invalid/');
 await page.evaluate(edge=>{window.__quotaMonitorV2Thread='one';localStorage.setItem('cti-layout-v2',JSON.stringify({expanded:{edge,y:80}}));localStorage.setItem('cti-edge-dock','true');localStorage.setItem('cti-language','zh');},edge);
 const bridge=fs.readFileSync(path.join(__dirname,'../quota_monitor/page_bridge.js'),'utf8');
 const call=opts=>page.evaluate(({bridge,opts})=>(0,eval)(bridge)(opts),{bridge,opts:{expected:'http://edge.invalid/',key:'one',...opts}});
 assert.equal(await call({action:'initialize',consumer:{source:fs.readFileSync(process.argv[2],'utf8')}}),'ready');
 const root=page.locator('.cti-hud'),mascot=page.locator('#codex-context-token-inspector-mascot');
 await mascot.focus();await mascot.click();await page.locator('[data-settings-toggle]').click();
 await page.evaluate(()=>{window.edgeErrors=[];window.addEventListener('error',e=>edgeErrors.push(e.message));window.originalSet=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k==='cti-edge-dock')throw Error('full');return originalSet.call(this,k,v);};});
 await page.locator('[data-edge-dock]').uncheck();
 assert.equal(await root.getAttribute('data-docked'),null);assert.equal(await root.getAttribute('data-dock-pinned'),null);
 assert.equal(await mascot.getAttribute('data-visible'),'false');
 await page.locator('[data-language]').selectOption('en');
 assert.equal(await page.locator('[data-edge-dock]').isChecked(),false);
 assert.equal(await page.evaluate(()=>localStorage.getItem('cti-edge-dock')),'true');
 await page.evaluate(()=>{Storage.prototype.setItem=originalSet;});
 await page.locator('[data-edge-dock]').check();
 assert.equal(await root.getAttribute('data-docked'),null,'enabling permits future docking, not immediate relocation');
 assert.equal(await page.evaluate(()=>localStorage.getItem('cti-edge-dock')),'true');
 await page.locator('[data-edge-dock]').uncheck();
 assert.equal(await page.evaluate(()=>localStorage.getItem('cti-edge-dock')),'false');
 assert.deepEqual(await page.evaluate(()=>edgeErrors),[]);
 await page.waitForFunction(()=>{const n=document.querySelector('.cti-hud');return Math.abs(n.getBoundingClientRect().left-parseFloat(n.style.left))<1;});
 if(process.argv[3]){fs.mkdirSync(process.argv[3],{recursive:true});await page.evaluate(()=>document.documentElement.style.colorScheme='light dark');for(const colorScheme of ['light','dark']){await page.emulateMedia({colorScheme});await page.screenshot({path:path.join(process.argv[3],`${engine.name()}-${edge}-${colorScheme}.png`)});}}
 await page.close();console.log(engine.name()+' '+edge+': failed write undocks, language keeps choice, recovery and no forced redock passed');
}}finally{await browser.close();}}})().catch(e=>{console.error(e);process.exitCode=1;});
