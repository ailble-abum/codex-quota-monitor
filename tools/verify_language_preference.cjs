const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../quota_monitor/panel_language.js'), 'utf8');
function fixture(value, html = '', browser = 'en-US') {
  const state = {value, writes: [], failRead: false, failWrite: false};
  const context = vm.createContext({document: {documentElement: {lang: html}}, navigator: {language: browser}, localStorage: {
    getItem(key) { assert.equal(key, 'cti-language'); if (state.failRead) throw Error('denied'); return state.value; },
    setItem(key, value) { assert.equal(key, 'cti-language'); if (state.failWrite) throw Error('full'); state.writes.push(value); state.value = value; }
  }});
  vm.runInContext(source, context);
  return {state, context};
}
for (const value of ['auto', 'zh', 'en', null, '', 'invalid']) {
  const {state, context} = fixture(value, 'zh-CN');
  assert.equal(context.languagePreference(), ['auto','zh','en'].includes(value) ? value : 'auto');
  assert.equal(context.uiLanguage(), value === 'en' ? 'en' : 'zh');
  assert.deepEqual(state.writes, []);
  assert.equal(context.setLanguagePreference('invalid'), false);
  assert.deepEqual(state.writes, []);
}
assert.equal(fixture('auto', '', 'zh-TW').context.uiLanguage(), 'zh');
assert.equal(fixture('auto', 'fr', 'zh-TW').context.uiLanguage(), 'en');
const {state, context} = fixture('en', 'zh-CN');
state.failRead = true;
assert.equal(context.uiLanguage(), 'zh');
state.failRead = false; state.failWrite = true;
assert.equal(context.setLanguagePreference('zh'), false);
assert.equal(context.uiLanguage(), 'zh');
assert.equal(state.value, 'en');
state.failRead = true;
assert.equal(context.languagePreference(), 'zh');
state.failRead = false; state.failWrite = false;
assert.equal(context.setLanguagePreference('en'), true);
state.value = 'auto';
assert.equal(context.languagePreference(), 'auto');
assert.equal(context.uiLanguage(), 'zh');
assert.equal(fixture('en').context.uiLanguage(), 'en');
console.log('language: valid/invalid, automatic resolution, denied reads/writes, recovery and instance isolation passed');
