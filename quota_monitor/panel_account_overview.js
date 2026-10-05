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
      : (zh ? '预计还能用 ' : 'about ');
    return prefix + durationPhrase(budget.seconds);
  }

  function renderAccountOverview(body, quota, live, blocked, contextSource) {
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
    const source = node('cti-source-row');
    source.append(badge('official', contextSource === 'chatgpt'
      ? text('Codex 额度', 'Codex quota') : text('账户额度', 'Account quota')));
    next.append(source);
    const windows = live ? quota.windows : [];
    if (windows.length) {
      const reset = blocked ? nearestResetText(windows) : '';
      const note = blocked ? text('额度已用完', 'Quota exhausted') +
        (reset ? text('，重置于 ', ' · resets ') + reset : text('，等待重置', '')) : accountBudgetText(quota);
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
      const status = quota.status === 'loading' ? text('正在读取额度…', 'Reading quota…')
        : live && quota.windowStatus === 'not_reported' ? text('账户未提供额度数据', 'No quota data reported')
        : text('额度暂不可用', 'Quota unavailable');
      next.append(node('cti-muted', status));
    }
    if (live && windows.length > 1) next.append(node('cti-muted', text('每个周期都需有剩余额度。', 'All periods need remaining quota.')));
    if (live && !windows.length && blocked) next.append(node('cti-muted', text('额度已用完，等待重置。', 'Quota exhausted. Wait for a reset.')));
    if (live) {
      const parts = [], usage = quota.usage;
      const daily = Array.isArray(usage?.dailyUsageBuckets) ? usage.dailyUsageBuckets : [];
      const last = daily[daily.length - 1]?.tokens, total = usage?.summary?.lifetimeTokens;
      if (Number.isFinite(last) && last >= 0) parts.push(`${text('最近日用量', 'Latest daily')} ${token(last)}`);
      if (Number.isFinite(total) && total >= 0) parts.push(`${text('累计 Token', 'Lifetime tokens')} ${token(total)}`);
      const credits = quota.resetCredits;
      if (Number.isSafeInteger(credits?.availableCount) && credits.availableCount >= 0) {
        let label = `${text('重置次数', 'Reset credits')} ${credits.availableCount}`;
        const expiry = credits.nextExpiresAt;
        if (Number.isFinite(expiry) && expiry >= 0 && expiry <= 8.64e12)
          label += ` · ${text('到期', 'expires')} ${new Date(expiry * 1000).toLocaleString(zh ? 'zh-CN' : 'en', {month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})}`;
        parts.push(label);
      }
      if (parts.length || windows.length) {
        const details = document.createElement('details');
        details.className = 'cti-account-breakdown';
        details.open = current.querySelector('.cti-account-breakdown')?.open === true;
        const summary = document.createElement('summary');
        summary.textContent = text('账户明细', 'Account details');
        details.append(summary);
        const periods = document.createElement('div');
        periods.innerHTML = accountWindowHTML(windows, blocked, undefined, true);
        details.append(...periods.childNodes);
        if (parts.length) {
          const usage = node('cti-account-quota');
          for (const part of parts) usage.append(node('cti-account-stat', part));
          details.append(usage);
        }
        next.append(details);
      }
    }
    if (!current.isEqualNode(next)) current.replaceChildren(...next.childNodes);
  }
