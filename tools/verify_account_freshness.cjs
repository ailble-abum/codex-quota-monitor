const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../quota_monitor/panel_account_status.js'), 'utf8'), context);
for (const [updatedAt, live, age] of [[1000,true,0],[999.5,true,0],[880.001,true,119],[880,false,120],[879,false,121],
  [1000.001,false,null],[undefined,false,null],[null,false,null],['999',false,null],[NaN,false,null],[Infinity,false,null],[-Infinity,false,null]]) {
  const result = context.accountFreshness({status: 'live', updatedAt}, 1000);
  assert.equal(result.live, live, String(updatedAt)); assert.equal(result.age, age, String(updatedAt));
}
for (const quota of [null, undefined, {}, {status:'loading',updatedAt:1000}, {status:'error',updatedAt:1000}]) {
  assert.equal(context.accountFreshness(quota, 1000).live, false);
}
assert.equal(context.accountFreshness({status:'live',updatedAt:1000}, NaN).live, false);
console.log('freshness: missing, invalid, future, exact 120-second boundary and status checks passed');
