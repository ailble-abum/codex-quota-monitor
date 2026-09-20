const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const context=vm.createContext({MASCOT_EXPRESSIONS:{cat:{idle:'data:image/test'}},MASCOT_ART:{},
  MASCOT_SKINS:{cat:{zh:'猫',en:'Cat',accent:'#fff',ring:[10,12,8]},plain:{zh:'素',en:'Plain',accent:'#000',ring:[1,2,3]}},
  language:'en',uiLanguage:()=>context.language});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../quota_monitor/panel_companion_view.js'),'utf8'),context);
assert.equal(context.companionScale(0.75,300,300),0.75); assert.equal(context.companionScale(2,300,300),2);
assert.equal(context.companionScale(null,720,450),1); assert.equal(context.companionScale(null,2160,1350),1.5);
assert.equal(context.mascotArt('cat'),'data:image/test'); assert.equal(context.mascotArt('missing'),'');
assert.ok(context.mascotMarkup('cat','art').includes('<img class="art"'));
assert.ok(context.mascotMarkup('plain','art').includes('🐾'));
let buttons=context.skinButtons(); assert.ok(buttons.includes('data-skin-choice="cat"')); assert.ok(buttons.includes('<small>Cat</small>'));
context.language='zh'; buttons=context.skinButtons(); assert.ok(buttons.includes('<small>猫</small>'));
console.log('companion view: manual/automatic scale, art fallback and bilingual skin controls passed');
