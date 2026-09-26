const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = {dataset:{}, querySelectorAll:()=>[]};
const context = vm.createContext({window:{innerWidth:1000,innerHeight:900}, edge:true,
  edgeDockEnabled:()=>context.edge});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../quota_monitor/panel_geometry.js'), 'utf8'), context);

assert.equal(context.hudMode(root),'expanded'); assert.equal(context.hudBase(root),292);
root.dataset.collapsed='true'; assert.equal(context.hudMode(root),'compact'); assert.equal(context.hudBase(root),180);
root.querySelectorAll=()=>new Array(4); assert.equal(context.hudBase(root),345);
assert.equal(context.dockSafeTop(),64); context.window.innerHeight=90; assert.equal(context.dockSafeTop(),8);
assert.equal(context.dockVerticalY(-10,900,300),64); assert.equal(context.dockVerticalY(800,900,300),592);
assert.equal(context.compactDockPanelY(180,52,56),178);
assert.equal(context.compactDockPanelY(180,104,56),204);
assert.deepEqual(JSON.parse(JSON.stringify(context.mascotDragGeometry({pointerY:10,top:80,moved:false},13,900,300))),{moved:false,y:80});
assert.deepEqual(JSON.parse(JSON.stringify(context.mascotDragGeometry({pointerY:10,top:80,moved:false},20,900,300))),{moved:true,y:90});
context.window.innerWidth=1000; assert.equal(context.dockCandidate(8,20,200,300),'left');
assert.equal(context.dockCandidate(792,20,200,300),'right'); assert.equal(context.dockCandidate(300,20,200,300),null);
context.edge=false; assert.equal(context.dockCandidate(8,20,200,300),null); context.edge=true;
assert.equal(context.presetWidth(root,'mini'),283); assert.equal(context.presetWidth(root,'large'),414);
assert.deepEqual(JSON.parse(JSON.stringify(context.resizeGeometry({x:200,y:200,left:100,right:400,width:300},250,210,'se',1000))),{left:100,width:350});
assert.deepEqual(JSON.parse(JSON.stringify(context.resizeGeometry({x:200,y:200,left:100,right:400,width:300},250,210,'sw',1000))),{left:150,width:250});
assert.deepEqual(JSON.parse(JSON.stringify(context.contextHintGeometry({left:950,right:990,top:850,bottom:890,height:40},{width:200,height:100},{width:1000,height:900},null))),{left:792,top:742});
assert.deepEqual(JSON.parse(JSON.stringify(context.contextHintGeometry({left:8,right:56,top:80,bottom:128,height:48},{width:200,height:100},{width:1000,height:900},'left'))),{left:64,top:68});
console.log('geometry: modes, bounds, drag threshold, docking, resize and hints passed');
