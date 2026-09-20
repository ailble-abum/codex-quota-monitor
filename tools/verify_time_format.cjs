const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const context = vm.createContext({language: 'en'});
context.uiLanguage = () => context.language;
vm.runInContext(fs.readFileSync(path.join(__dirname, '../quota_monitor/panel_time.js'), 'utf8'), context);
for (const [value, expected] of [[-1,'0m'],[0,'0m'],[1,'<1m'],[59,'<1m'],[60,'1m'],
  [90,'2m'],[3569,'59m'],[3570,'1.0h'],[35999,'10.0h'],[36000,'10h'],
  [86399,'24h'],[86400,'1d'],[129600,'2d']]) {
  assert.equal(context.shortDuration(value), expected, `short ${value}`);
}
for (const language of ['en','zh']) {
  context.language = language;
  const zh = language === 'zh';
  for (const [value,en,cn] of [[0,'under a minute','不足 1 分钟'],[-1,'under a minute','不足 1 分钟'],
    [1,'0 min','0 分钟'],[30,'1 min','1 分钟'],[3599,'60 min','60 分钟'],
    [3600,'1.0 hours','1.0 小时'],[172799,'48.0 hours','48.0 小时'],[172800,'2.0 days','2.0 天']]) {
    assert.equal(context.durationPhrase(value), zh ? cn : en);
  }
  for (const [duration,label] of [[300,'5h'],[10080,'7d'],[1440,'1d'],[120,'2h'],[90,'90m'],[1.5,'1.5m']]) {
    assert.equal(context.windowLabel({duration}), label + (zh ? ' 剩余' : ' remaining'));
    assert.equal(context.windowLabel({duration},true), label + (zh ? ' 剩余' : ' left'));
  }
  for (const duration of [null,undefined,NaN,Infinity,-Infinity,'300',true,0,-1,[],{}]) {
    assert.equal(context.windowLabel({duration,key:'primary'}), zh ? '主窗口 剩余' : 'Primary remaining');
    assert.equal(context.windowLabel({duration,key:'secondary'},true), zh ? '次窗口 剩余' : 'Secondary left');
  }
  assert.equal(context.windowLabel(null), zh ? '次窗口 剩余' : 'Secondary remaining');
  for (const input of [null,undefined,NaN,Infinity,-Infinity,'60',true,[],{}]) {
    assert.equal(context.shortDuration(input), '-');
    assert.equal(context.durationPhrase(input), '-');
  }
  const stamp = 1700000000;
  const expected = new Date(stamp*1000).toLocaleString(zh ? 'zh-CN' : 'en',
    {month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'});
  const windows = [{resetsAt:stamp+3600},null,{resetsAt:NaN},{resetsAt:-1},{resetsAt:8.64e12+1},
    {resetsAt:Infinity},{resetsAt:String(stamp-1)},{resetsAt:stamp}];
  assert.equal(context.nearestResetText(windows), expected);
  assert.equal(windows[0].resetsAt, stamp+3600, 'input order unchanged');
  for (const input of [null,undefined,{},'bad',[],[{resetsAt:NaN}],[{resetsAt:-1}],
    [{resetsAt:8.64e12+1}],[{}]]) {
    assert.equal(context.nearestResetText(input), '');
  }
  assert.notEqual(context.nearestResetText([{resetsAt:0}]), '', 'Unix epoch is valid');
  const upperLimit = context.nearestResetText([{resetsAt:8.64e12}]);
  assert.notEqual(upperLimit, '');
  assert.notEqual(upperLimit, 'Invalid Date');
}
console.log('time format: bilingual boundaries, labels, strict values and earliest valid reset passed');
