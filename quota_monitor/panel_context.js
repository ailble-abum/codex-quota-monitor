  // Snapshot selection remains the caller's responsibility; this owns presentation only.
  function renderContext(body, summary) {
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
      next.append(element('span', 'cti-muted', tr('noRecords')));
    } else {
      const heading = element('div', 'cti-line');
      const label = document.createElement('span');
      const badge = element('span', 'cti-trust', zh ? '本地会话' : 'Local session');
      badge.dataset.kind = 'local';
      label.append(badge, document.createTextNode(zh ? ' 上下文最近观测' : ' Last observed context'));
      heading.append(label, element('span', 'cti-value', pct(value)));
      next.append(heading);
      if (value === null) {
        next.append(element('div', 'cti-muted', zh ? '上下文占用暂不可用' : 'Context usage unavailable'));
      } else {
        const meter = element('div', 'cti-meter');
        for (const [key, attribute] of Object.entries({role: 'meter', 'aria-label': zh ? '上下文占用' : 'Context used',
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
