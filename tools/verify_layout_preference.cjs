const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../quota_monitor/panel_layout_preference.js'),'utf8');
const state={value:'invalid',writes:[],failRead:false};
const context=vm.createContext({LAYOUT_PRESET_KEY:'preset',localStorage:{getItem:()=>{if(state.failRead)throw Error('denied');return state.value;}}});
vm.runInContext(source,context);
for(const value of ['mini','standard','large','invalid',null]){state.value=value;assert.equal(context.layoutPreset(),['mini','standard','large'].includes(value)?value:'standard');}
state.failRead=true;assert.equal(context.layoutPreset(),'standard');state.failRead=false;
const buttons=['mini','standard','large'].map(value=>({dataset:{layoutPreset:value},attrs:{},setAttribute(key,value){this.attrs[key]=value;}}));
for(const value of ['mini','standard','large']){state.value=value;context.updatePresetButtons({querySelectorAll:()=>buttons});for(const button of buttons){assert.equal(button.dataset.active,String(button.dataset.layoutPreset===value));assert.equal(button.attrs['aria-pressed'],button.dataset.active);}}
console.log('layout preference: valid/invalid/missing, denied read and selected/ARIA projection passed');
state.value='standard';state.failWrite=true;
context.localStorage.setItem=(key,value)=>{if(state.failWrite)throw Error('full');state.writes.push([key,value]);if(key==='preset')state.value=value;};
assert.equal(context.setLayoutPreference('large'),false);
assert.equal(context.layoutPreset(),'large');
assert.equal(state.value,'standard');
assert.equal(context.setLayoutPreference('invalid'),false);
const root={__ctiLayout:{expanded:{x:12,y:50,width:350}}};
assert.equal(context.saveLayout(root),false);
assert.equal(root.__ctiLayout.expanded.width,350);
state.failWrite=false;
assert.equal(context.setLayoutPreference('mini'),true);
assert.equal(context.saveLayout(root),true);
assert.deepEqual(state.writes,[['preset','mini'],['cti-layout-v2',JSON.stringify(root.__ctiLayout)]]);
state.value='standard';assert.equal(context.layoutPreset(),'standard');
root.__ctiLayout.circular=root.__ctiLayout;
assert.equal(context.saveLayout(root),false);
console.log('layout writes: temporary preset, rejected input, in-memory geometry, recovery and serialization failure passed');
