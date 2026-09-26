const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const style = {setProperty(key,value){this[key]=value;}};
const mascot = {dataset:{skin:'cat'},style:{setProperty(key,value){this[key]=value;}},setAttribute(){},matches:()=>false};
const root = {dataset:{collapsed:'false'},style,__ctiLayout:{expanded:{x:900,y:850,width:292}},
  querySelectorAll:()=>[],matches:()=>false,
  getBoundingClientRect(){return {left:Number.parseFloat(style.left)||0,top:Number.parseFloat(style.top)||0,width:Number.parseFloat(style.width)||292,height:300,right:(Number.parseFloat(style.left)||0)+(Number.parseFloat(style.width)||292)};}};
const context = vm.createContext({window:{innerWidth:1000,innerHeight:900},document:{getElementById:()=>mascot},
  MASCOT_ID:'mascot',clearTimeout,setTimeout,positionContextHint:()=>{},updateMascotSizeControls:()=>{},
  edge:true,edgeDockEnabled:()=>context.edge,mascotScale:()=>1,mascotSkin:()=>'cat',applyMascotSkin:()=>{},ensureMascot:()=>mascot,
  hudMode:r=>r.dataset.collapsed==='true'?'compact':'expanded',hudBase:()=>292,dockSafeTop:()=>64,
  dockVerticalY:(y,h,p,m=48)=>Math.max(64,Math.min(h-Math.max(p,m)-8,y)),initialPanelLayout:()=>({}),saved:0,saveLayout:()=>context.saved++,
  presetWidth:()=>350,setLayoutPreference:()=>{},updatePresetButtons:()=>{}});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../quota_monitor/panel_layout_runtime.js'),'utf8'),context);

context.applyStoredHudPosition(root);
assert.equal(style.left,'700px'); assert.equal(style.top,'592px'); assert.equal(style.width,'292px');
root.__ctiLayout.expanded={edge:'left',y:880,width:300}; context.applyStoredHudPosition(root);
assert.equal(root.dataset.docked,'true'); assert.equal(root.dataset.revealed,'false');
assert.equal(mascot.dataset.visible,'true'); assert.equal(style.left,'-302px');
assert.equal(style.top,'592px'); assert.equal(mascot.style.top,'840px');
context.revealDock(root,true); assert.equal(root.dataset.revealed,'true'); assert.equal(style.left,'60px');
context.undockHud(root); assert.equal(root.dataset.docked,undefined); assert.equal(mascot.dataset.visible,'false');
assert.equal(root.__ctiLayout.expanded.edge,undefined); assert.ok(context.saved>0);
root.__ctiLayout.expanded={x:20,y:80}; context.setLayoutPreset(root,'large');
assert.equal(root.__ctiLayout.expanded.width,350); const saved=context.saved;
context.setLayoutPreset(root,'bogus'); assert.equal(context.saved,saved);
root.__ctiLayout.expanded.edge='left'; root.dataset.docked='true'; root.dataset.dockPinned='true'; context.revealDock(root,false);
assert.equal(root.dataset.revealed,'false'); context.clearDockHide(root); assert.equal(root.__ctiDockHideTimer,null);
console.log('layout runtime: viewport clamp, dock reveal, undock, preset and timer cleanup passed');
