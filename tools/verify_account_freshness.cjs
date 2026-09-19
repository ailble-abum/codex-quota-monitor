const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../quota_monitor/panel_account_status.js'), 'utf8'), context);
for (const [updatedAt, live, age] of [[1000,true,0],[999.5,true,0],[880.001,true,119],[880,false,120],[879,false,121],
  [1000.001,false,null],[undefined,false,null],[null,false,null],['999',false,null],[NaN,false,null],[Infinity,false,null],[-Infinity,false,null]]) {
  const result = context.accountFreshness({status: 'live', updatedAt, windows: []}, 1000);
  assert.equal(result.live, live, String(updatedAt)); assert.equal(result.age, age, String(updatedAt));
}
for (const quota of [null, undefined, {}, {status:'loading',updatedAt:1000,windows:[]}, {status:'error',updatedAt:1000,windows:[]}]) {
  assert.equal(context.accountFreshness(quota, 1000).live, false);
}
assert.equal(context.accountFreshness({status:'live',updatedAt:1000,windows:[]}, NaN).live, false);
console.log('freshness: missing, invalid, future, exact 120-second boundary and status checks passed');

const validWindow = {remaining: 80, duration: 300, resetsAt: 2000, paceDelta: -2, projectedExhaustAt: 1800, exhaustInSec: 800};
for (const windows of [[], [validWindow], [{remaining: 0}], [{remaining: 100}]]) {
  assert.equal(context.accountFreshness({status: 'live', updatedAt: 1000, windows}, 1000).live, true);
}
for (const windows of [undefined, null, {}, 'bad', [null], [80], new Array(1),
  [{remaining: '80'}], [{remaining: NaN}], [{remaining: Infinity}], [{remaining: -1}], [{remaining: 101}],
  [validWindow, {remaining: -1}], [{...validWindow, duration: 0}], [{...validWindow, resetsAt: Infinity}],
  [{...validWindow, projectedExhaustAt: 1e20}], [{...validWindow, paceDelta: '2'}], [{...validWindow, exhaustInSec: -1}]]) {
  assert.equal(context.accountFreshness({status: 'live', updatedAt: 1000, windows}, 1000).live, false);
}
console.log('windows: complete valid groups only; malformed and mixed-invalid groups rejected');
