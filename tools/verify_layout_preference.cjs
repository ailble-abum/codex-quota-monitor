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
