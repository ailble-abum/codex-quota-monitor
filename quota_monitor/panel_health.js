  // Local-log presentation only; this does not infer compaction or handoff policy.
  function renderHealth(body, health) {
    const current = body.querySelector('[data-health]');
    const next = current.cloneNode(false);
    const zh = uiLanguage() === 'zh';
    const text = (chinese, english) => zh ? chinese : english;
    const count = health == null ? 0 : health.count;
    const valid = Number.isSafeInteger(count) && count >= 0;
    const warning = valid && count > 0 && health?.recommendHandoff === true;
    next.dataset.warning = String(warning);
    next.title = text('压缩次数和压后首请求来自本地日志；上下文变化不等于会话累计 Token。',
      'Compaction counts and first requests come from local logs; context changes are not session token totals.');
    if (warning) {
      const reasons = {
        baseline: text('建议依据：压缩后首请求仍占上下文窗口至少 40%。这是经验阈值，不是官方上限。',
          'Basis: the first post-compaction request still uses at least 40% of context. This is a heuristic, not an official limit.'),
        frequency: text('建议依据：最近两次压缩间隔均不超过 5 个不同请求。这是经验阈值。',
          'Basis: each of the last two compaction intervals contains at most 5 distinct requests. This is a heuristic.'),
      };
      next.title = Object.hasOwn(reasons, health.reason) ? reasons[health.reason]
        : text('交接建议依据未提供；不能据此推断官方上限。', 'Handoff basis unavailable; no official limit can be inferred.');
    }
    const element = (tag, className, content) => {
      const node = document.createElement(tag); node.className = className; node.textContent = content; return node;
    };
    const row = element('div', 'cti-source-row', '');
    const badge = element('span', 'cti-trust', text('本地日志', 'Local logs'));
    badge.dataset.kind = 'local'; row.append(badge); next.append(row);
    if (!valid || count === 0) {
      next.append(element('span', 'cti-muted', valid
        ? text('尚未观察到压缩事件', 'No observed compaction events')
        : text('压缩数据暂不可用', 'Compaction data unavailable')));
    } else {
      let baseline = text('等待后续请求', 'Awaiting next request');
      if (health.after != null) {
        const percent = Number.isFinite(health.afterPercent) && health.afterPercent >= 0 && health.afterPercent <= 100
          ? pct(health.afterPercent) : '-';
        baseline = Number.isFinite(health.after) && health.after >= 0
          ? `${token(health.after)} (${percent})` : text('压后请求数据暂不可用', 'Post-compaction data unavailable');
      }
      next.append(document.createTextNode(`${text('已观察压缩', 'Compactions observed')} ${count}${zh ? ' 次' : ''}`),
        document.createElement('br'), document.createTextNode(`${text('压后首请求', 'First request after compression')} ${baseline}`),
        document.createElement('br'), element('span', 'cti-muted', text('含系统与工具，不等于摘要本身大小。', 'Includes system/tools; not summary-only size.')));
      if (warning) next.append(document.createElement('br'), element('strong', '',
        text('建议整理交接，换新任务继续', 'Consider a handoff to a new task')));
    }
    if (current.dataset.warning !== next.dataset.warning) current.dataset.warning = next.dataset.warning;
    if (current.title !== next.title) current.title = next.title;
    if (!current.isEqualNode(next)) current.replaceChildren(...next.childNodes);
  }
