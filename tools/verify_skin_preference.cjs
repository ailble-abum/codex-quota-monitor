const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../quota_monitor/panel_skin_preference.js'),'utf8');
let value=null,fail=false,deny=false,writes=0;
const ctx=vm.createContext({SKIN_KEY:'skin',MASCOT_SKINS:{cat:{zh:'猫',en:'Cat'},candy:{zh:'糖',en:'Candy'}},localStorage:{getItem:()=>{if(deny)throw Error('denied');return value;},setItem:(_,v)=>{if(fail)throw Error('full');value=v;writes++;}}});vm.runInContext(source,ctx);
for(const v of [null,'invalid','constructor','__proto__','toString','cat','candy']){value=v;assert.equal(ctx.mascotSkin(),v==='candy'?'candy':'cat');}
assert.equal(writes,0);deny=true;assert.equal(ctx.mascotSkin(),'cat');deny=false;
value='cat';fail=true;assert.equal(ctx.setMascotSkin('candy'),false);assert.equal(ctx.mascotSkin(),'candy');assert.equal(value,'cat');
for(const v of ['constructor','__proto__','unknown',null])assert.equal(ctx.setMascotSkin(v),false);
assert.equal(ctx.mascotSkin(),'candy');fail=false;assert.equal(ctx.setMascotSkin('cat'),true);value='candy';assert.equal(ctx.mascotSkin(),'candy');
console.log('skin preference: registry-only keys, defaults, denied reads/writes, temporary choice and recovery passed');
