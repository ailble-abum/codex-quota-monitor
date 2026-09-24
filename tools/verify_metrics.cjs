const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const context = vm.createContext({language:'en', uiLanguage:()=>context.language,
  I18N:{en:{unknown:'UNKNOWN',high:'HIGH',watch:'WATCH',ok:'OK',sample:'Sample'},zh:{unknown:'未知',high:'高',watch:'注意',ok:'正常',sample:'示例'}},
  accountFreshness:quota=>({live:quota.status==='live'}), window:{}});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../quota_monitor/panel_metrics.js'), 'utf8'), context);
assert.equal(context.tr('sample'), 'Sample'); assert.equal(context.tr('missing'), 'missing');
context.language='zh'; assert.equal(context.tr('sample'), '示例');
for(const [value,tone] of [[undefined,'unknown'],[NaN,'unknown'],[-1,'low'],[20,'low'],[20.1,'watch'],[50,'watch'],[50.1,'safe']]) assert.equal(context.quotaTone(value),tone);
for(const [value,meter,tone] of [[undefined,null,'unknown'],[-1,0,'safe'],[69.9,69.9,'safe'],[70,70,'watch'],[85,85,'low'],[101,100,'low']]){assert.equal(context.contextMeterValue(value),meter);assert.equal(context.contextTone(value),tone);}
assert.equal(context.accountTone({},80,false),'unknown'); assert.equal(context.accountTone({ordinaryUsageAllowed:false},80,true),'low'); assert.equal(context.accountTone({},80,true),'safe');
assert.equal(context.toneLabel('other'),'尚未更新'); assert.equal(context.pressure(85),'高'); assert.equal(context.pressure(70),'注意'); assert.equal(context.pressure(0),'正常');
assert.equal(context.remainingContext({latest_context_tokens:70,context_window:100}),30); assert.equal(context.remainingContext({latest_context_tokens:120,context_window:100}),0); assert.equal(context.remainingContext({latest_context_tokens:'70',context_window:100}),null);
assert.equal(context.gaugeColor('safe'),'var(--cti-safe)'); assert.match(context.gaugeColor('unknown'),/color-mix/);
context.window.__codexContextTokenInspectorPayload={quota:{status:'live',windows:[{remaining:80}],ordinaryUsageAllowed:false}};
assert.deepEqual(JSON.parse(JSON.stringify(context.gaugeReading())),{quota:{status:'live',windows:[{remaining:80}],ordinaryUsageAllowed:false},live:true,windows:[{remaining:80}],blocked:true});
context.window.__codexContextTokenInspectorPayload.quota.status='error'; assert.deepEqual(JSON.parse(JSON.stringify(context.gaugeReading().windows)),[]);
console.log('metrics: labels, thresholds, clamping, remaining context and gauge state passed');
