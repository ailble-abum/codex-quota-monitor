  // A reset time alone is not evidence of how long remaining quota will last.
  function windowBudgetText(item, now = Date.now() / 1000) {
    const estimate = item?.exhaustInSec;
    if (!Number.isFinite(estimate) || estimate < 0) return null;
    const untilReset = Number.isFinite(item.resetsAt) ? item.resetsAt - now : NaN;
    if (untilReset > 0 && estimate >= untilReset) return `≥${shortDuration(untilReset)}`;
    return shortDuration(estimate);
  }

  function accountBudgetText(quota) {
    const budget = quota?.budget;
    if (!budget || !['floor', 'exhaust'].includes(budget.kind) ||
        !Number.isFinite(budget.seconds) || budget.seconds < 0) return '';
    const zh = uiLanguage() === 'zh';
    const prefix = budget.kind === 'floor' ? (zh ? '至少还能用 ' : 'at least ')
      : (zh ? '按当前速度还能用 ' : 'at this pace about ');
    return prefix + durationPhrase(budget.seconds);
  }

  function renderAccountOverview(body, quota, live, blocked) {
    const current = body.querySelector('[data-quota]'), next = current.cloneNode(false);
    const zh = uiLanguage() === 'zh';
    const text = (chinese, english) => zh ? chinese : english;
    const node = (className, content) => {
      const result = document.createElement('div'); result.className = className;
      if (content !== undefined) result.textContent = content;
      return result;
    };
    const badge = (kind, label) => {
      const result = document.createElement('span'); result.className = 'cti-trust';
      result.dataset.kind = kind; result.textContent = label; return result;
    };
    const source = node('cti-source-row'); source.append(badge('official', text('官方账户', 'Official account'))); next.append(source);
    const windows = live ? quota.windows : [];
    if (windows.length) {
      const reset = blocked ? nearestResetText(windows) : '';
      const note = blocked ? text('账户已达上限', 'Account at its limit') +
        (reset ? text('，最近重置 ', ' · nearest reset ') + reset : text('，等待重置', '')) : accountBudgetText(quota);
      if (note) {
        const budget = node('cti-quota-budget');
        budget.dataset.tone = blocked ? 'low' : quotaTone(Math.min(...windows.map(item => item.remaining)));
        if (!blocked) budget.append(badge('estimate', text('估算', 'Estimate')), document.createTextNode(' '));
        budget.append(document.createTextNode(note)); next.append(budget);
      }
      // Only V2's text-built window serializer supplies this fragment.
      const cards = document.createElement('div'); cards.innerHTML = accountWindowHTML(windows, blocked);
      next.append(...cards.childNodes);
    } else {
      const status = quota.status === 'loading' ? text('正在读取账户配额…', 'Reading quota…')
        : live && quota.windowStatus === 'not_reported' ? text('账户未报告周期配额窗口', 'No periodic quota windows reported')
        : text('暂时无法读取配额', 'Quota: unavailable');
      next.append(node('cti-muted', status));
    }
    if (live && windows.length > 1) next.append(node('cti-muted', text('所有窗口均需有余量才能继续。', 'Every window must have headroom to continue.')));
    if (live && !windows.length && blocked) next.append(node('cti-muted', text('账户当前已达上限。', 'The account is at its limit right now.')));
    if (live) {
      const parts = [], usage = quota.usage;
      const daily = Array.isArray(usage?.dailyUsageBuckets) ? usage.dailyUsageBuckets : [];
      const last = daily[daily.length - 1]?.tokens, total = usage?.summary?.lifetimeTokens;
      if (Number.isFinite(last) && last >= 0) parts.push(`${text('最近日用量', 'Latest daily')} ${token(last)}`);
      if (Number.isFinite(total) && total >= 0) parts.push(`${text('累计活动', 'Lifetime activity')} ${token(total)}`);
      const credits = quota.resetCredits;
      if (Number.isSafeInteger(credits?.availableCount) && credits.availableCount >= 0) {
        let label = `${text('可用重置额度', 'Reset credits')} ${credits.availableCount}`;
        const expiry = credits.nextExpiresAt;
        if (Number.isFinite(expiry) && expiry >= 0 && expiry <= 8.64e12)
          label += ` · ${text('最近到期', 'next expiry')} ${new Date(expiry * 1000).toLocaleString(zh ? 'zh-CN' : 'en', {month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})}`;
        parts.push(label);
      }
      if (parts.length) next.append(node('cti-account-quota', parts.join(' · ')));
    }
    if (!current.isEqualNode(next)) current.replaceChildren(...next.childNodes);
  }
