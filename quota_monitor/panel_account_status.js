  function validAccountWindows(windows) {
    if (!Array.isArray(windows)) return false;
    for (const item of windows) {
      if (!item || typeof item !== 'object' || Array.isArray(item) ||
          !Number.isFinite(item.remaining) || item.remaining < 0 || item.remaining > 100) return false;
      if (item.duration != null && (!Number.isFinite(item.duration) || item.duration <= 0)) return false;
      if (item.paceDelta != null && !Number.isFinite(item.paceDelta)) return false;
      if (item.exhaustInSec != null && (!Number.isFinite(item.exhaustInSec) || item.exhaustInSec < 0)) return false;
      for (const timestamp of [item.resetsAt, item.projectedExhaustAt]) {
        if (timestamp != null && (!Number.isFinite(timestamp) || timestamp < 0 || timestamp > 8.64e12)) return false;
      }
    }
    return true;
  }

  function accountFreshness(quota, now = Date.now() / 1000) {
    const timestamp = quota?.updatedAt;
    const elapsed = Number.isFinite(timestamp) && Number.isFinite(now) ? now - timestamp : NaN;
    const validTime = Number.isFinite(elapsed) && elapsed >= 0;
    return {age: validTime ? Math.floor(elapsed) : null,
      live: quota?.status === 'live' && validTime && elapsed < 120 && validAccountWindows(quota.windows)};
  }

  // Account freshness comes from the shared predicate; this function only renders text.
  function renderAccountStatus(body, quota, live, age) {
    const zh = uiLanguage() === 'zh';
    const text = (chinese, english) => zh ? chinese : english;
    let message;
    if (live) {
      const plan = typeof quota.planType === 'string' ? quota.planType : '';
      const planLabel = plan ? ` · ${plan[0].toUpperCase()}${plan.slice(1)}` : '';
      const updated = age < 10 ? text('刚刚更新', 'just updated') : `${age}s ${text('前更新', 'ago')}`;
      message = `${text('账户接口', 'Account')}${planLabel} · ${updated}`;
    } else {
      const errors = {
        cli_missing: text('找不到 Codex CLI', 'Codex CLI missing'),
        timeout: text('账户读取超时', 'Account read timed out'),
        app_server: text('App Server 不可用', 'App Server unavailable'),
        account_unavailable: text('账户暂不可用', 'Account unavailable'),
      };
      const code = typeof quota.errorCode === 'string' ? quota.errorCode : '';
      const error = code ? ` · ${Object.hasOwn(errors, code) ? errors[code] : code}` : '';
      message = `${text('账户配额未更新', 'Account unavailable')}${error} · ${text('本地 Token 独立读取', 'local tokens independent')}`;
    }
    const node = body.querySelector('[data-freshness]');
    if (node.textContent !== message) node.textContent = message;
  }
