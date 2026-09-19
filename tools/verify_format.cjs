// Behavioral contract, independent of the retained renderer's implementation.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../quota_monitor/panel_format.js'), 'utf8');
for (const locale of ['en-US', 'de-DE', 'zh-CN']) {
  const context = vm.createContext({mode: 'auto', unitMode: () => context.mode,
    Intl: {NumberFormat: function(_, options) { return new Intl.NumberFormat(locale, options); }}});
  vm.runInContext(source, context);
  const check = (mode, input, output) => {
    context.mode = mode;
    assert.equal(context.token(input), output, `${locale} ${mode} ${input}`);
  };
  const comma = locale === 'de-DE';
  check('auto', 0, '0'); check('auto', 999, '999'); check('auto', 1000, '1K');
  check('auto', 1250, comma ? '1,3K' : '1.3K');
  check('auto', 1000000, '1M'); check('auto', -1250000, comma ? '-1,3M' : '-1.3M');
  check('raw', 1234.567, comma ? '1.234,567' : '1,234.567');
  check('k', 99999, comma ? '100,00K' : '100.00K');
  check('k', 100000, comma ? '100,0K' : '100.0K');
  check('k', 1000000, comma ? '1.000K' : '1,000K');
  check('m', 1000000, '1.00M'); check('m', 10000000, '10.0M');
  check('m', -10000000, '-10.0M');
  assert.equal(context.pct(50), '50.0%'); assert.equal(context.pct(0), '0.0%');
  for (const value of [null, undefined, NaN, Infinity, -Infinity, '', '123', true, {}, []]) {
    for (const mode of ['auto', 'raw', 'k', 'm']) check(mode, value, '-');
    assert.equal(context.pct(value), '-');
  }
}
console.log('format: three locales, unit thresholds, rounding, signs and invalid values passed');
