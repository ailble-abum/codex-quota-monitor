const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium,webkit}=require('playwright');
const source=['panel_format.js','panel_account_status.js','panel_account_overview.js'].map(name=>fs.readFileSync(path.join(__dirname,'../quota_monitor',name),'utf8')).join('\n');
(async()=>{for(const engine of [chromium,webkit]){
 const browser=await engine.launch();try{
  const page=await browser.newPage();await page.setContent('<main><div data-quota></div></main>');
  await page.evaluate(source=>{window.uiLanguage=()=>window.language;window.unitMode=()=> 'auto';window.durationPhrase=n=>`${n}s`;
   window.accountWindowHTML=()=>'<div class="cti-quota-window">windows</div>';window.nearestResetText=()=>'';window.quotaTone=()=> 'safe';(0,eval)(source);},source);
  for(const language of ['zh','en']){
   const render=(quota,live=true,blocked=false)=>page.evaluate(({quota,live,blocked,language})=>{
    window.language=language;const body=document.querySelector('main');renderAccountOverview(body,quota,live,blocked);
    const node=body.firstChild,first=node.firstChild;renderAccountOverview(body,quota,live,blocked);
    return {text:node.textContent,extra:node.querySelector('.cti-account-quota')?.textContent||'',stable:first===node.firstChild};
   },{quota,live,blocked,language});
   const quota={windows:[{remaining:80},{remaining:60}],budget:{kind:'floor',seconds:60},usage:{dailyUsageBuckets:[{tokens:1000}],summary:{lifetimeTokens:2000}},resetCredits:{availableCount:2,nextExpiresAt:1000}};
   let result=await render(quota);assert.equal(result.stable,true);assert.ok(result.extra.includes('1K'));assert.ok(result.extra.includes('2K'));assert.ok(result.text.includes('60s'));
   result=await render(quota,false);assert.equal(result.extra,'');assert.equal(result.text.includes('60s'),false);
   result=await render({...quota,budget:{kind:'floor',seconds:Infinity},usage:{dailyUsageBuckets:[{tokens:-1}],summary:{lifetimeTokens:'20'}},resetCredits:{availableCount:1.5,nextExpiresAt:Infinity}});
   assert.equal(result.extra,'');assert.equal(result.text.includes('Infinity'),false);
   for (const budget of [{kind:'unknown',seconds:60},{kind:'floor',seconds:-1},{kind:'exhaust',seconds:'60'}]) {
    result=await render({...quota,budget});assert.equal(result.text.includes('60s'),false);
   }
   result=await render({...quota,budget:{kind:'exhaust',seconds:60},resetCredits:{availableCount:0,nextExpiresAt:Infinity}});
   assert.ok(result.text.includes('60s'));assert.equal(result.extra.includes('Invalid Date'),false);
   result=await render({windows:[],status:'live',windowStatus:'not_reported'},true,true);
   assert.ok(result.text.includes(language==='zh'?'已达上限':'at its limit'));
   result=await render({windows:[],status:'loading'},false);
   assert.ok(result.text.includes(language==='zh'?'正在读取':'Reading quota'));
  }
  console.log(engine.name()+': account overview valid/stale/invalid values, blocked empty windows, bilingual and stable nodes passed');
 }finally{await browser.close();}
}})().catch(error=>{console.error(error);process.exitCode=1;});
