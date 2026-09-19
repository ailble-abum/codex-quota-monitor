  // Project session details as text: model/provider strings never become HTML.
  function renderSessionDetails(body, summary) {
    const currentMetrics = body.querySelector('[data-metrics]');
    const currentExplanation = body.querySelector('[data-explanation]');
    if (!summary) {
      if (currentMetrics.hasChildNodes()) currentMetrics.replaceChildren();
      if (currentExplanation.hasChildNodes()) currentExplanation.replaceChildren();
      return;
    }
    const metrics = currentMetrics.cloneNode(false);
    const explanation = currentExplanation.cloneNode(false);
    for (const [label, value] of [[tr('turn'), summary.latest_turn_total_tokens],
                                 [tr('session'), summary.session_total_tokens]]) {
      const card = document.createElement('div');
      card.className = 'cti-metric';
      for (const [className, text] of [['cti-muted', label], ['cti-value', token(value)]]) {
        const span = document.createElement('span');
        span.className = className;
        span.textContent = text;
        card.append(span);
      }
      metrics.append(card);
    }
    const zh = uiLanguage() === 'zh';
    const input = summary.latest_turn_input_tokens;
    const cached = summary.latest_turn_cached_input_tokens;
    const share = Number.isFinite(input) && input > 0 && Number.isFinite(cached) && cached >= 0
      ? pct(Math.min(1, cached / input) * 100) : '—';
    const name = value => typeof value === 'string' && value ? value : '—';
    const lines = [
      `${tr('input')}: ${token(input)} · ${tr('cachedInput')}: ${token(cached)} · ${tr('output')}: ${token(summary.latest_turn_output_tokens)}`,
      `${zh ? '模型' : 'Model'}: ${name(summary.model)} · ${zh ? '推理强度' : 'Reasoning'}: ${name(summary.reasoning_effort)}`,
      `${zh ? '缓存占比' : 'Cached input share'}: ${share}`,
      zh ? '缓存已包含在输入内。会话累计不等于上下文占用；Token 不可换算为账户剩余配额。'
         : 'Cached tokens are part of input. Session totals differ from context usage. Tokens do not convert to account quota.',
    ];
    lines.forEach((line, index) => {
      if (index) explanation.append(document.createElement('br'));
      explanation.append(document.createTextNode(line));
    });
    for (const [current, next] of [[currentMetrics, metrics], [currentExplanation, explanation]]) {
      if (!current.isEqualNode(next)) current.replaceChildren(...next.childNodes);
    }
  }
