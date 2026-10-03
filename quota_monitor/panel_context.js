  // Snapshot selection remains the caller's responsibility; this owns presentation only.
  function renderContext(body, summary, source) {
    const current = body.querySelector('[data-context]');
    const next = current.cloneNode(false);
    const zh = uiLanguage() === 'zh';
    const element = (tag, className, text) => {
      const node = document.createElement(tag);
      node.className = className;
      if (text !== undefined) node.textContent = text;
      return node;
    };
    const percent = summary?.latest_context_percent;
    const value = Number.isFinite(percent) ? Math.min(100, Math.max(0, percent)) : null;
    const tone = value === null ? 'unknown' : value < 70 ? 'safe' : value < 85 ? 'watch' : 'low';
    next.dataset.tone = summary ? tone : 'unknown';
    if (!summary) {
      next.append(element('span', 'cti-muted', source === 'chatgpt'
        ? zh ? 'ChatGPT 未提供上下文数据' : 'ChatGPT context data is unavailable'
        : tr('noRecords')));
    } else {
      const heading = element('div', 'cti-line');
      const label = document.createElement('span');
      const badge = element('span', 'cti-trust', zh ? '当前聊天' : 'Current chat');
      badge.dataset.kind = 'local';
      label.append(badge, document.createTextNode(zh ? ' 上下文已用' : ' Context used'));
      heading.append(label, element('span', 'cti-value', pct(value)));
      next.append(heading);
      if (value === null) {
        next.append(element('div', 'cti-muted', zh ? '上下文暂不可读' : 'Context usage unavailable'));
      } else {
        const meter = element('div', 'cti-meter');
        for (const [key, attribute] of Object.entries({role: 'meter', 'aria-label': zh ? '上下文已用' : 'Context used',
          'aria-valuemin': '0', 'aria-valuemax': '100', 'aria-valuenow': String(value)})) meter.setAttribute(key, attribute);
        const fill = document.createElement('span');
        fill.style.width = `${value}%`;
        meter.append(fill);
        next.append(meter, element('div', 'cti-muted', `${token(summary.latest_context_tokens)} / ${token(summary.context_window)} · Token`));
      }
    }
    if (current.dataset.tone !== next.dataset.tone) current.dataset.tone = next.dataset.tone;
    if (!current.isEqualNode(next)) current.replaceChildren(...next.childNodes);
  }
