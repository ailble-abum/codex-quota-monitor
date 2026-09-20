  // V2 display labels and meter semantics. Invalid values stay unavailable.
  function tr(key) {
    const table = I18N[uiLanguage()] || I18N.en;
    return table[key] || I18N.en[key] || key;
  }
  function labeled(key, value) {
    return uiLanguage() === 'zh' ? `${tr(key)}：${value}` : `${tr(key)}: ${value}`;
  }
  function parenthesized(value) {
    return uiLanguage() === 'zh' ? `（${value}）` : `(${value})`;
  }
  function joined(values) { return values.join(uiLanguage() === 'zh' ? '，' : ', '); }

  function quotaTone(remaining) {
    if (!Number.isFinite(remaining)) return 'unknown';
    if (remaining <= 20) return 'low';
    return remaining <= 50 ? 'watch' : 'safe';
  }
  function contextMeterValue(used) {
    return Number.isFinite(used) ? Math.min(100, Math.max(0, used)) : null;
  }
  function contextTone(used) {
    const value = contextMeterValue(used);
    if (value === null) return 'unknown';
    if (value >= 85) return 'low';
    return value >= 70 ? 'watch' : 'safe';
  }
  function accountTone(quota, remaining, live) {
    if (!live) return 'unknown';
    return quota?.ordinaryUsageAllowed === false || quota?.rateLimitReachedType
      ? 'low' : quotaTone(remaining);
  }
  function toneLabel(tone) {
    const labels = uiLanguage() === 'zh'
      ? {safe:'余量充足', watch:'留意用量', low:'额度偏低', unknown:'尚未更新'}
      : {safe:'Comfortable', watch:'Watch usage', low:'Running low', unknown:'Unavailable'};
    return labels[tone] || labels.unknown;
  }
  function pressure(value) {
    if (!Number.isFinite(value)) return tr('unknown');
    return tr(value >= 85 ? 'high' : value >= 70 ? 'watch' : 'ok');
  }
  function remainingContext(item) {
    const used = item?.latest_context_tokens;
    const limit = item?.context_window;
    return Number.isFinite(used) && Number.isFinite(limit) ? Math.max(0, limit - used) : null;
  }
  function gaugeColor(tone) {
    const colors = {low:'var(--cti-low)', watch:'var(--cti-watch)', safe:'var(--cti-safe)'};
    return colors[tone] || 'color-mix(in srgb,CanvasText 45%,transparent)';
  }
  function gaugeReading() {
    const quota = window.__codexContextTokenInspectorPayload?.quota || {};
    const live = accountFreshness(quota).live;
    return {quota, live, windows:live ? quota.windows : [],
      blocked:live && (quota.ordinaryUsageAllowed === false || Boolean(quota.rateLimitReachedType))};
  }
