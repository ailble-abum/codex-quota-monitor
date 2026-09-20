const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../quota_monitor/panel_templates.js'),'utf8'),context);
const html = context.panelHeader();
for (const marker of ['data-cti-title','data-refresh','data-settings-toggle','data-cti-toggle','data-cti-body'])
  assert.equal((html.match(new RegExp(marker,'g')) || []).length,1,marker);
for (const unit of ['auto','raw','k','m']) assert.ok(html.includes(`data-cti-unit="${unit}"`));
assert.equal((html.match(/class="cti-unit-group"/g)||[]).length,1);
assert.ok(html.indexOf('data-cti-title') < html.indexOf('data-cti-body'));
console.log('templates: owned header shell exposes one title, controls, unit group and body mount');
context.skinButtons=()=>'<button data-skin-choice="cat"><small>Cat</small></button>';
const body=context.panelBodyTemplate(true);
for(const marker of ['data-quota','data-freshness','data-context','data-health','data-details','data-metrics','data-explanation','data-settings','data-units','data-language','data-layout-preset','data-edge-dock','data-mascot-scale','data-skins','data-alerts','data-handoff','data-position-reset','data-build','data-update','data-dom'])
  assert.ok(body.includes(marker),marker);
assert.ok(body.includes('data-alerts disabled'));
assert.ok(body.includes('id="cti-quota-alerts-unavailable"'));
assert.ok(body.includes('data-skin-choice="cat"'));
console.log('templates: owned body exposes rendering, settings, skin and diagnostics mounts');
