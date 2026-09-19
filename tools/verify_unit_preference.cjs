const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../quota_monitor/panel_controls.js'), 'utf8');
const key = 'unit';
function fixture(value) {
  const state = {value, writes: [], failRead: false, failWrite: false};
  const context = vm.createContext({UNIT_KEY: key, localStorage: {
    getItem(name) { assert.equal(name, key); if (state.failRead) throw Error('denied'); return state.value; },
    setItem(name, value) { assert.equal(name, key); if (state.failWrite) throw Error('full'); state.writes.push(value); state.value = value; }
  }});
  vm.runInContext(source, context);
  return {state, context};
}
for (const value of ['auto', 'raw', 'k', 'm', null, '', 'invalid']) {
  const {state, context} = fixture(value);
  assert.equal(context.unitMode(), ['auto', 'raw', 'k', 'm'].includes(value) ? value : 'auto');
  assert.deepEqual(state.writes, []);
  assert.equal(context.setUnitMode('m'), true);
  assert.equal(context.unitMode(), 'm');
  assert.equal(context.setUnitMode('invalid'), false);
  assert.equal(context.unitMode(), 'm');
  assert.deepEqual(state.writes, ['m']);
}
const {state, context} = fixture('raw');
state.failRead = true;
assert.equal(context.unitMode(), 'auto');
state.failRead = false; state.failWrite = true;
assert.equal(context.setUnitMode('k'), false);
assert.equal(context.unitMode(), 'k'); // stale persisted raw must not win
state.failRead = true;
assert.equal(context.unitMode(), 'k');
state.failRead = false; state.failWrite = false;
assert.equal(context.setUnitMode('m'), true);
state.value = 'auto'; // external preference edits remain visible after a successful write
assert.equal(context.unitMode(), 'auto');
assert.equal(fixture('raw').context.unitMode(), 'raw'); // fallback is instance-local
console.log('unit preference: valid/missing/invalid, no initialization writes, denied reads/writes, recovery passed');
