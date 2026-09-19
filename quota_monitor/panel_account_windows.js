  // Called only with the complete window group accepted by accountFreshness.
  // Serialize text-built nodes for the retained account section's comparison/update.
  function accountWindowHTML(windows, blocked, now = Date.now() / 1000) {
    const zh = uiLanguage() === 'zh';
    const text = (chinese, english) => zh ? chinese : english;
    const node = (tag, className, content) => {
      const result = document.createElement(tag); result.className = className;
      if (content !== undefined) result.textContent = content;
      return result;
    };
    const date = stamp => new Date(stamp * 1000).toLocaleString(zh ? 'zh-CN' : 'en',
      {month:'numeric', day:'numeric', hour:'2-digit', minute:'2-digit'});
    const container = document.createElement('div');
    for (const item of windows) {
      const label = windowLabel(item);
      const tone = blocked ? 'low' : quotaTone(item.remaining);
      const windowNode = node('div', 'cti-quota-window'); windowNode.dataset.tone = tone;
      const heading = node('div', 'cti-line');
      const value = node('span', 'cti-value cti-quota-value', String(Math.round(item.remaining)));
      value.append(document.createElement('small')); value.lastChild.textContent = '%';
      heading.append(node('span', '', label), value);
      const meter = node('div', 'cti-meter');
      for (const [key, value] of Object.entries({role:'meter', 'aria-label':label, 'aria-valuemin':'0',
        'aria-valuemax':'100', 'aria-valuenow':String(item.remaining)})) meter.setAttribute(key, value);
      const fill = document.createElement('span'); fill.style.width = `${item.remaining}%`; meter.append(fill);
      let pace = '';
      if (item.paceDelta != null) {
        const delta = item.paceDelta;
        pace = Math.abs(delta) < 2 ? text('符合均匀进度', 'On steady pace')
          : `${delta > 0 ? text('快于均匀进度', 'Ahead of pace') : text('慢于均匀进度', 'Behind pace')} ${Math.round(Math.abs(delta))}pt`;
      }
      const status = node('div', 'cti-line'); status.style.marginBottom = '6px';
      status.append(node('span', 'cti-status', toneLabel(tone)), node('span', 'cti-muted', pace));
      let countdown = '';
      if (item.resetsAt != null) {
        const minutes = Math.max(0, Math.ceil((item.resetsAt - now) / 60));
        if (minutes === 0) countdown = text('等待刷新', 'Awaiting refresh');
        else if (minutes < 60) countdown = `${minutes}${text(' 分钟后', ' min')}`;
        else if (minutes < 1440) countdown = `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
        else countdown = `${Math.floor(minutes / 1440)}${text(' 天 ', 'd ')}${Math.floor(minutes % 1440 / 60)}h`;
      }
      const timing = node('div', 'cti-muted', `${item.resetsAt == null ? '—' : date(item.resetsAt)} ${text('重置', 'reset')} · ${countdown}`);
      if (item.projectedExhaustAt != null) timing.append(document.createElement('br'),
        document.createTextNode(`${text('按当前速度预计', 'At current pace')} ${date(item.projectedExhaustAt)} ${text('耗尽', 'exhausted')}`));
      windowNode.append(heading, meter, status, timing); container.append(windowNode);
    }
    return container.innerHTML;
  }
