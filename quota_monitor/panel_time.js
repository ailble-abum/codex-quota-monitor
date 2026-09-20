  // V2 time display: seconds for budgets, minutes for window lengths.
  // Keep valid-value presentation stable; never coerce strings or missing data.
  function shortDuration(value) {
    if (!Number.isFinite(value)) return '-';
    if (value <= 0) return '0m';
    if (value < 60) return '<1m';
    const minutes = Math.round(value / 60);
    const unit = minutes < 60 ? 'm' : value < 86400 ? 'h' : 'd';
    const amount = value / {m:60, h:3600, d:86400}[unit];
    return (unit === 'h' && amount < 10 ? amount.toFixed(1) : String(Math.round(amount))) + unit;
  }

  function durationPhrase(value) {
    if (!Number.isFinite(value)) return '-';
    const chinese = uiLanguage() === 'zh';
    if (value <= 0) return chinese ? '不足 1 分钟' : 'under a minute';
    const [divisor, zh, en] = value < 3600 ? [60, '分钟', 'min']
      : value < 172800 ? [3600, '小时', 'hours'] : [86400, '天', 'days'];
    const amount = value / divisor;
    return `${divisor === 60 ? Math.round(amount) : amount.toFixed(1)} ${chinese ? zh : en}`;
  }

  function windowLabel(item, compact = false) {
    const chinese = uiLanguage() === 'zh';
    const minutes = item?.duration;
    let label = item?.key === 'primary' ? (chinese ? '主窗口' : 'Primary')
      : (chinese ? '次窗口' : 'Secondary');
    if (Number.isFinite(minutes) && minutes > 0) {
      const [size, suffix] = [[1440, 'd'], [60, 'h'], [1, 'm']]
        .find(([size]) => size === 1 || minutes % size === 0);
      label = `${minutes / size}${suffix}`;
    }
    return label + (chinese ? ' 剩余' : compact ? ' left' : ' remaining');
  }

  function nearestResetText(windows) {
    if (!Array.isArray(windows)) return '';
    let earliest = Infinity;
    for (const item of windows) {
      const stamp = item?.resetsAt;
      if (Number.isFinite(stamp) && stamp >= 0 && stamp <= 8.64e12 && stamp < earliest)
        earliest = stamp;
    }
    if (earliest === Infinity) return '';
    return new Date(earliest * 1000).toLocaleString(uiLanguage() === 'zh' ? 'zh-CN' : 'en',
      {month:'numeric', day:'numeric', hour:'2-digit', minute:'2-digit'});
  }
