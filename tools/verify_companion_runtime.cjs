const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const image={value:'',getAttribute(){return this.value;},set src(value){this.value=value;},get src(){return this.value;}};
const mascot={dataset:{skin:'cat',mood:'idle'},querySelector:selector=>selector==='img'?image:null};
const context=vm.createContext({MASCOT_ID:'mascot',MASCOT_EXPRESSIONS:{cat:{idle:'idle',happy:'happy',pet:'pet',notice:'notice',waiting:'waiting',concerned:'concerned'}},
  document:{getElementById:()=>mascot},motion:true,companionPreference:name=>name==='motion'?context.motion:true,
  setTimeout,clearTimeout});
for(const file of ['panel_companion_behavior.js','panel_companion_runtime.js']) vm.runInContext(fs.readFileSync(path.join(__dirname,'../quota_monitor',file),'utf8'),context);
context.applyCompanionExpression(mascot); assert.equal(image.src,'idle'); assert.equal(mascot.dataset.expression,'idle');
context.companionReact({},'hello'); assert.equal(mascot.dataset.reaction,'hello'); assert.equal(image.src,'happy'); assert.ok(mascot.__ctiReactionTimer);
clearTimeout(mascot.__ctiReactionTimer); delete mascot.dataset.reaction; context.motion=false;
context.companionReact({},'notice'); assert.equal(mascot.dataset.reaction,undefined);
const source=fs.readFileSync(path.join(__dirname,'../quota_monitor/panel_companion_runtime.js'),'utf8');
for(const event of ['pointerenter','pointerleave','pointerdown','pointermove','pointerup','pointercancel','click','focus','blur']) assert.ok(source.includes(`'${event}'`),event);
for(const cleanup of ['__ctiPetTimer','__ctiReactionTimer','__ctiClearHint']) assert.ok(source.includes(cleanup),cleanup);
assert.equal(source.includes('style.cssText'),false);
console.log('companion runtime: expression/reaction projection, motion opt-out, DOM events and cleanup hooks passed');
