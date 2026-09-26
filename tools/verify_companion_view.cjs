const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const context=vm.createContext({MASCOT_EXPRESSIONS:{cat:{idle:'data:image/test'}},MASCOT_ART:{},
  MASCOT_SKINS:{cat:{zh:'猫',en:'Cat',accent:'#fff',ring:[10,12,8]},plain:{zh:'素',en:'Plain',accent:'#000',ring:[1,2,3]}},
  language:'en',uiLanguage:()=>context.language,
  windowLabel:item=>item.label,windowBudgetText:item=>item.budget});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../quota_monitor/panel_companion_view.js'),'utf8'),context);
assert.equal(context.companionScale(0.75,300,300),0.75); assert.equal(context.companionScale(2,300,300),2);
assert.equal(context.companionScale(null,720,450),1); assert.equal(context.companionScale(null,2160,1350),1.5);
assert.equal(context.mascotArt('cat'),'data:image/test'); assert.equal(context.mascotArt('missing'),'');
assert.ok(context.mascotMarkup('cat','art').includes('<img class="art"'));
assert.ok(context.mascotMarkup('plain','art').includes('🐾'));
let buttons=context.skinButtons(); assert.ok(buttons.includes('data-skin-choice="cat"')); assert.ok(buttons.includes('<small>Cat</small>'));
context.language='zh'; buttons=context.skinButtons(); assert.ok(buttons.includes('<small>猫</small>'));
let readings=context.companionWindowReadings([{label:'5h left',remaining:51,budget:'1.6h'},{label:'7d left',remaining:82,budget:'4d'}],71,false);
assert.deepEqual(JSON.parse(JSON.stringify(readings)),['5h left 1.6h','7d left 4d','CTX 71%']);
assert.equal(readings.some(item=>item.includes('51%')||item.includes('82%')),false);
readings=context.companionWindowReadings([{label:'5h 剩余',remaining:51,budget:null}],null,true);
assert.deepEqual(JSON.parse(JSON.stringify(readings)),['5h 剩余 时间估算暂不可用']);
// Periodic numeric updates must retain the current image/gauge nodes and reaction.
let replacements=0;
const image={complete:true};
const mascot={dataset:{},style:{setProperty(){}},querySelector:()=>image,
  set innerHTML(value){replacements++;}};
context.ensureMascot=()=>mascot; context.mascotSkin=()=> 'cat';
context.queueMicrotask=()=>{}; context.positionContextHint=()=>{};
context.applyMascotContext=()=>{}; context.applyCompanionExpression=()=>{};
context.applyMascotSkin({});
assert.equal(replacements,1);
mascot.dataset.reaction='pet';
context.applyMascotSkin({}); context.applyMascotSkin({});
assert.equal(replacements,1);
assert.equal(mascot.dataset.reaction,'pet');
context.language='en'; context.applyMascotSkin({});
assert.equal(replacements,2);
assert.ok(mascot.dataset.skinLabel.startsWith('Cat'));
console.log('companion view: manual/automatic scale, art fallback and bilingual skin controls passed');
