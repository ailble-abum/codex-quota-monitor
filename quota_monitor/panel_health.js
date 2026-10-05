  // Local-log presentation only; this does not infer compaction or handoff policy.
  function renderHealth(body, health) {
    const current = body.querySelector('[data-health]');
    const next = current.cloneNode(false);
    const zh = uiLanguage() === 'zh';
    const text = (chinese, english) => zh ? chinese : english;
    const count = health == null ? 0 : health.count;
    const valid = Number.isSafeInteger(count) && count >= 0;
    const warning = valid && count > 0 && health?.recommendHandoff === true;
    // Empty history is available in the data, but needs no second empty-state row.
    next.hidden = valid && count === 0;
    next.dataset.warning = String(warning);
    next.title = text('压缩数据来自聊天记录；上下文与聊天累计用量不同。',
      'Compaction data comes from chat logs. Context differs from total chat usage.');
    if (warning) {
      const reasons = {
        baseline: text('压缩后首轮仍占至少 40% 上下文。经验建议，非官方限制。',
          'The first turn after compaction still uses at least 40% of context. A guideline, not an official limit.'),
        frequency: text('最近两次压缩间隔均不超过 5 次请求。经验建议。',
          'The last two compaction intervals each span 5 requests or fewer. A guideline.'),
      };
      next.title = Object.hasOwn(reasons, health.reason) ? reasons[health.reason]
        : text('交接依据未知，非官方限制。', 'Handoff basis unknown; not an official limit.');
    }
    const element = (tag, className, content) => {
      const node = document.createElement(tag); node.className = className; node.textContent = content; return node;
    };
    const row = element('div', 'cti-source-row', '');
    const badge = element('span', 'cti-trust', text('聊天记录', 'Chat logs'));
    badge.dataset.kind = 'local'; row.append(badge); next.append(row);
    if (!valid || count === 0) {
      next.append(element('span', 'cti-muted', valid
        ? text('暂无压缩记录', 'No compaction recorded')
        : text('压缩记录暂不可用', 'Compaction data unavailable')));
    } else {
      let baseline = text('等待下一轮', 'Awaiting next turn');
      if (health.after != null) {
        const percent = Number.isFinite(health.afterPercent) && health.afterPercent >= 0 && health.afterPercent <= 100
          ? pct(health.afterPercent) : '-';
        baseline = Number.isFinite(health.after) && health.after >= 0
          ? `${token(health.after)} (${percent})` : text('压缩后用量暂不可读', 'Post-compaction data unavailable');
      }
      next.append(document.createTextNode(`${text('上下文压缩', 'Context compactions')} ${count}${zh ? ' 次' : ''}`),
        document.createElement('br'), document.createTextNode(`${text('压缩后首轮', 'First turn after compaction')} ${baseline}`),
        document.createElement('br'), element('span', 'cti-muted', text('含系统和工具，非摘要大小。', 'Includes system/tools, not just the summary.')));
      if (warning) next.append(document.createElement('br'), element('strong', '',
        text('建议交接到新聊天', 'Consider a handoff to a new chat')));
    }
    if (current.dataset.warning !== next.dataset.warning) current.dataset.warning = next.dataset.warning;
    if (current.title !== next.title) current.title = next.title;
    if (current.hidden !== next.hidden) current.hidden = next.hidden;
    if (!current.isEqualNode(next)) current.replaceChildren(...next.childNodes);
  }
