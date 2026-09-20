const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../quota_monitor/panel_scale_preference.js'),'utf8');
const state={value:null,failRead:false,failWrite:false,writes:[]};
const context=vm.createContext({MASCOT_SCALE_KEY:'scale',innerWidth:900,innerHeight:700,companionScale:(value)=>value===null?1:value,localStorage:{getItem:()=>{if(state.failRead)throw Error('denied');return state.value;},setItem:(key,value)=>{if(state.failWrite)throw Error('full');state.value=value;state.writes.push(value);},removeItem:()=>{if(state.failWrite)throw Error('denied');state.value=null;state.writes.push(null);}}});
vm.runInContext(source,context);
for(const [value,expected] of [[null,null],['invalid',null],['0.74',null],['2.01',null],['0.75',.75],['2',2]]){state.value=value;assert.equal(context.mascotScalePreference(),expected);}
state.failRead=true;assert.equal(context.mascotScalePreference(),null);state.failRead=false;
state.value='1.25';state.failWrite=true;
assert.equal(context.setMascotScalePreference(2),false);assert.equal(context.mascotScale(),2);assert.equal(state.value,'1.25');
assert.equal(context.setMascotScalePreference(null),false);assert.equal(context.mascotScale(),1);assert.equal(state.value,'1.25');
for(const value of [-1,3,NaN,Infinity,'1'])assert.equal(context.setMascotScalePreference(value),false);
assert.equal(context.mascotScalePreference(),null);
state.failWrite=false;assert.equal(context.setMascotScalePreference(.75),true);assert.equal(state.value,'0.75');
assert.equal(context.setMascotScalePreference(null),true);assert.equal(state.value,null);
state.value='1.5';assert.equal(context.mascotScale(),1.5);
console.log('scale preference: bounds, missing/invalid, read denial, temporary manual/auto, recovery passed');
