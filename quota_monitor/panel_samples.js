  // V2-owned local sample summary. The numeric digest stays small and never
  // exposes paths or raw session records to the panel.
  function renderLocalSamples(body, samples) {
    const current = body.querySelector('[data-history]');
    if (!current) return;
    const next = current.cloneNode(false);
    const zh = uiLanguage() === 'zh';
    const text = (chinese, english) => zh ? chinese : english;
    const valid = samples && Number.isSafeInteger(samples.samples) && samples.samples > 0;
    if (!valid) {
      const empty = document.createElement('span');
      empty.className = 'cti-muted';
      empty.textContent = text('本地历史未启用或暂无采样', 'Local history is disabled or has no samples');
      next.append(empty);
    } else {
      const title = document.createElement('div');
      title.className = 'cti-line';
      const label = document.createElement('span');
      label.textContent = text('本地历史', 'Local history');
      const count = document.createElement('span');
      count.className = 'cti-value'; count.textContent = `${samples.samples}`;
      title.append(label, count); next.append(title);
      const values = [];
      if (Number.isFinite(samples.spanSeconds) && samples.spanSeconds > 0)
        values.push(`${text('覆盖', 'span')} ${shortDuration(samples.spanSeconds)}`);
      if (Number.isFinite(samples.minRemaining))
        values.push(`${text('最低余量', 'min left')} ${Math.round(samples.minRemaining)}%`);
      if (Number.isFinite(samples.peakContext))
        values.push(`${text('上下文峰值', 'peak context')} ${Math.round(samples.peakContext)}%`);
      if (Number.isFinite(samples.averageCachedShare))
        values.push(`${text('平均缓存', 'cached avg')} ${Math.round(samples.averageCachedShare)}%`);
      const summary = document.createElement('p');
      summary.className = 'cti-muted'; summary.textContent = values.join(' · ') || text('历史数据不足', 'Not enough history yet');
      next.append(summary);
      if (Array.isArray(samples.models) && samples.models.length) {
        const models = document.createElement('p');
        models.className = 'cti-muted';
        models.textContent = `${text('模型', 'Models')}：${samples.models.join(' · ')}`;
        next.append(models);
      }
    }
    if (!current.isEqualNode(next)) current.replaceChildren(...next.childNodes);
  }
