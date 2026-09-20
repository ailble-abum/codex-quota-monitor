const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium,webkit}=require('playwright');
const source=['panel_format.js','panel_time.js','panel_account_status.js','panel_account_overview.js'].map(name=>fs.readFileSync(path.join(__dirname,'../quota_monitor',name),'utf8')).join('\n');
(async()=>{for(const engine of [chromium,webkit]){
 const browser=await engine.launch();try{
  const page=await browser.newPage();await page.setContent('<main><div data-quota></div></main>');
  await page.evaluate(source=>{window.uiLanguage=()=>window.language;window.unitMode=()=> 'auto';
   window.accountWindowHTML=()=>'<div class="cti-quota-window">windows</div>';window.quotaTone=()=> 'safe';(0,eval)(source);},source);
  assert.equal(await page.evaluate(()=>windowBudgetText({remaining:4,resetsAt:Date.now()/1000+500000})),null);
  assert.equal(await page.evaluate(()=>windowBudgetText({exhaustInSec:-1})),null);
  assert.equal(await page.evaluate(()=>windowBudgetText({exhaustInSec:60})),'1m');
  assert.equal(await page.evaluate(()=>windowBudgetText({exhaustInSec:600,resetsAt:1100},1000)),'≥2m');
  for(const language of ['zh','en']){
   const render=(quota,live=true,blocked=false)=>page.evaluate(({quota,live,blocked,language})=>{
    window.language=language;const body=document.querySelector('main');renderAccountOverview(body,quota,live,blocked);
    const node=body.firstChild,first=node.firstChild;renderAccountOverview(body,quota,live,blocked);
    return {text:node.textContent,extra:node.querySelector('.cti-account-quota')?.textContent||'',stable:first===node.firstChild};
   },{quota,live,blocked,language});
   const budgetText=language==='zh'?'1 分钟':'1 min';
   const quota={windows:[{remaining:80},{remaining:60}],budget:{kind:'floor',seconds:60},usage:{dailyUsageBuckets:[{tokens:1000}],summary:{lifetimeTokens:2000}},resetCredits:{availableCount:2,nextExpiresAt:1000}};
   let result=await render(quota);assert.equal(result.stable,true);assert.ok(result.extra.includes('1K'));assert.ok(result.extra.includes('2K'));assert.ok(result.text.includes(budgetText));
   result=await render(quota,false);assert.equal(result.extra,'');assert.equal(result.text.includes(budgetText),false);
   result=await render({...quota,budget:{kind:'floor',seconds:Infinity},usage:{dailyUsageBuckets:[{tokens:-1}],summary:{lifetimeTokens:'20'}},resetCredits:{availableCount:1.5,nextExpiresAt:Infinity}});
   assert.equal(result.extra,'');assert.equal(result.text.includes('Infinity'),false);
   for (const budget of [{kind:'unknown',seconds:60},{kind:'floor',seconds:-1},{kind:'exhaust',seconds:'60'}]) {
    result=await render({...quota,budget});assert.equal(result.text.includes(budgetText),false);
   }
   result=await render({...quota,budget:{kind:'exhaust',seconds:60},resetCredits:{availableCount:0,nextExpiresAt:Infinity}});
   assert.ok(result.text.includes(budgetText));assert.equal(result.extra.includes('Invalid Date'),false);
   result=await render({windows:[],status:'live',windowStatus:'not_reported'},true,true);
   assert.ok(result.text.includes(language==='zh'?'已达上限':'at its limit'));
   result=await render({windows:[],status:'loading'},false);
   assert.ok(result.text.includes(language==='zh'?'正在读取':'Reading quota'));
  }
  console.log(engine.name()+': account overview valid/stale/invalid values, blocked empty windows, bilingual and stable nodes passed');
 }finally{await browser.close();}
}})().catch(error=>{console.error(error);process.exitCode=1;});
