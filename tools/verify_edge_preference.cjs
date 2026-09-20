const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../quota_monitor/panel_edge_preference.js'),'utf8');
let value='true',fail=false,readFail=false;
const ctx=vm.createContext({EDGE_DOCK_KEY:'edge',localStorage:{getItem:()=>{if(readFail)throw Error('denied');return value;},setItem:(_,v)=>{if(fail)throw Error('full');value=v;}}});vm.runInContext(source,ctx);
for(const v of [null,'invalid','true','false']){value=v;assert.equal(ctx.edgeDockEnabled(),v!=='false');}
readFail=true;assert.equal(ctx.edgeDockEnabled(),true);readFail=false;
value='true';fail=true;assert.equal(ctx.setEdgeDockEnabled(false),false);assert.equal(ctx.edgeDockEnabled(),false);assert.equal(value,'true');
assert.equal(ctx.setEdgeDockEnabled('false'),false);assert.equal(ctx.edgeDockEnabled(),false);
fail=false;assert.equal(ctx.setEdgeDockEnabled(true),true);value='false';assert.equal(ctx.edgeDockEnabled(),false);
console.log('edge preference: defaults, read/write failures, transient choice and recovery passed');
