const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../quota_monitor/panel_position_reset.js'),'utf8');
for(const failed of [null,'position','cti-layout-v2','both']){
 const attempts=[],root={__ctiLayout:{expanded:{edge:'left'}},dataset:{docked:'true',dockEdge:'left',dockPinned:'true',revealed:'true'}};
 let clears=0,applied=0;
 const context=vm.createContext({POSITION_KEY:'position',localStorage:{removeItem:key=>{attempts.push(key);if(failed===key||failed==='both')throw Error('denied');}},clearDockHide:node=>{assert.equal(node,root);clears++;},applyStoredHudPosition:node=>{assert.equal(node,root);assert.deepEqual(Object.keys(node.__ctiLayout),[]);applied++;}});
 vm.runInContext(source,context);
 assert.equal(context.resetPanelPosition(root),failed===null);
 assert.deepEqual(attempts,['position','cti-layout-v2']);
 assert.deepEqual(root.dataset,{});assert.equal(clears,1);assert.equal(applied,1);
}
console.log('position reset: independent deletes, partial/all failures, transient layout and timer cleanup passed');
