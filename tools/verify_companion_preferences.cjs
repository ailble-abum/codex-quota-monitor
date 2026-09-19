const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../quota_monitor/panel_companion_preferences.js'),'utf8');
const keys={motion:'cti-companion-motion',reminders:'cti-companion-reminders',context:'cti-context-reminders'};
function fixture(){const state={values:{},writes:[],failRead:false,failWrite:false};const context=vm.createContext({localStorage:{getItem:key=>{if(state.failRead)throw Error('denied');return state.values[key];},setItem:(key,value)=>{if(state.failWrite)throw Error('full');state.values[key]=value;state.writes.push([key,value]);}}});vm.runInContext(source,context);return {state,context};}
for(const [name,key] of Object.entries(keys)){
 const {state,context}=fixture();
 for(const value of [undefined,'true','false','invalid']){state.values[key]=value;assert.equal(context.companionPreference(name),value!=='false');}
 assert.deepEqual(state.writes,[]);
 state.failRead=true;assert.equal(context.companionPreference(name),true);state.failRead=false;
 state.failWrite=true;assert.equal(context.setCompanionPreference(name,false),false);assert.equal(context.companionPreference(name),false);
 state.failRead=true;assert.equal(context.companionPreference(name),false);state.failRead=false;
 assert.equal(context.setCompanionPreference(name,'false'),false);assert.equal(context.companionPreference(name),false);
 state.failWrite=false;assert.equal(context.setCompanionPreference(name,true),true);state.values[key]='false';assert.equal(context.companionPreference(name),false);
 assert.equal(fixture().context.companionPreference(name),true);
}
assert.equal(fixture().context.setCompanionPreference('unknown',true),false);
console.log('companion preferences: defaults, per-key temporary choices, denied reads/writes, recovery and input validation passed');
