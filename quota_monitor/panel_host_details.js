  // V2-owned host projections. They are small, delegated and removable: no
  // observer, title rewrite or copied renderer code is needed for live rows.
  const HOST_NOTE_ATTR = 'data-cti-v2-sidebar-note';
  const HOST_CHIP_ATTR = 'data-cti-v2-token-chip';
  const HOST_TOOLTIP_ID = 'cti-v2-sidebar-tooltip';
  const HOST_MESSAGE_SELECTORS = [
    '[data-content-search-assistant-turn-key]',
    '[data-local-conversation-final-assistant]',
    '[data-chatgpt-conversation-turn="true"]',
  ];
  let hostListenersInstalled = false;

  function hostFinite(value) {
    return typeof value === 'number' && Number.isFinite(value);
  }

  function hostText(value) {
    return String(value == null ? '—' : value);
  }

  function hostThreadId(row) {
    return row.getAttribute('data-app-action-sidebar-thread-id') ||
      row.querySelector('[data-app-action-sidebar-thread-id]')?.getAttribute('data-app-action-sidebar-thread-id') || null;
  }

  function hostPercent(value) {
    return hostFinite(value) ? `${Number(value).toFixed(1)}%` : '—';
  }

  function hostNumber(value) {
    return hostFinite(value) ? token(value) : '—';
  }

  function hostSummaryNote(item) {
    const zh = uiLanguage() === 'zh';
    const parts = [
      `${zh ? '会话总计' : 'Session total'}  ${hostNumber(item.session_total_tokens)}`,
      `${zh ? '输入' : 'Input'}          ${hostNumber(item.session_input_tokens)}`,
      `${zh ? '缓存输入' : 'Cached input'}   ${hostNumber(item.session_cached_input_tokens)}`,
      `${zh ? '输出' : 'Output'}         ${hostNumber(item.session_output_tokens)}`,
      `${zh ? '推理' : 'Reasoning'}      ${hostNumber(item.session_reasoning_tokens)}`,
    ];
    return parts.join('\n');
  }

  function hostItems(payload) {
    const detail = payload?.detail;
    return detail && Array.isArray(detail.assistantItems) ? detail.assistantItems : [];
  }

  function hostMessageNodes() {
    const seen = new Set(), nodes = [];
    for (const selector of HOST_MESSAGE_SELECTORS) {
      document.querySelectorAll(selector).forEach(node => {
        const current = node.closest('[data-content-search-assistant-turn-key]') ||
          node.closest('[data-chatgpt-conversation-turn="true"]') || node;
        if (!seen.has(current)) { seen.add(current); nodes.push(current); }
      });
      if (nodes.length) break;
    }
    return nodes.filter(node => !node.closest(`#${ROOT_ID}`));
  }

  function hostActionRow(node) {
    const sent = node.querySelector('[data-assistant-message-sent-time]');
    if (sent?.parentElement) return sent.parentElement;
    return node.querySelector('.turn-action-controls') || null;
  }

  function hostPlainText(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function hostMatch(node, items, used, index) {
    const text = hostPlainText(node.textContent);
    for (let itemIndex = 0; itemIndex < items.length; itemIndex += 1) {
      if (used.has(itemIndex)) continue;
      const prefix = hostPlainText(items[itemIndex]?.textPrefix);
      if (prefix && text.includes(prefix)) { used.add(itemIndex); return items[itemIndex]; }
    }
    const fallback = items[Math.max(0, items.length - nodesForHostMatchCount() + index)];
    if (fallback) return fallback;
    return null;
  }

  function nodesForHostMatchCount() { return hostMessageNodes().length || 1; }

  function hostChipText(item, index) {
    const usage = item?.tokenUsage || {};
    const zh = uiLanguage() === 'zh';
    const current = `${hostNumber(usage.latest_context_tokens)}/${hostNumber(usage.context_window)} (${hostPercent(usage.latest_context_percent)})`;
    const total = `${hostNumber(usage.latest_turn_total_tokens)}/${hostNumber(usage.session_total_tokens)}`;
    const round = item?.assistantTurnIndex && item?.assistantTotalTurns
      ? `${zh ? '助手' : 'Assistant'} ${item.assistantTurnIndex}/${item.assistantTotalTurns}`
      : `${zh ? '助手' : 'Assistant'} ${index + 1}`;
    return `${zh ? 'Token' : 'Token'}: ${zh ? '当前' : 'Current'} ${current} | ${zh ? '总计' : 'Total'} ${total}   ${zh ? '轮次' : 'Rounds'}：${round}`;
  }

  function hostChipTitle(item) {
    const usage = item?.tokenUsage || {};
    const zh = uiLanguage() === 'zh';
    return [
      `${zh ? '上下文' : 'Context'}：${hostNumber(usage.latest_context_tokens)} / ${hostNumber(usage.context_window)} (${hostPercent(usage.latest_context_percent)})`,
      `${zh ? '本轮' : 'Turn'}：${hostNumber(usage.latest_turn_total_tokens)} ${zh ? 'Token' : 'tokens'}`,
      `${zh ? '会话' : 'Session'}：${hostNumber(usage.session_total_tokens)} ${zh ? 'Token' : 'tokens'}`,
    ].join('\n');
  }

  function removeHostTooltip() {
    document.getElementById(HOST_TOOLTIP_ID)?.remove();
  }

  function showHostTooltip(row) {
    const value = row.getAttribute(HOST_NOTE_ATTR);
    if (!value) return;
    removeHostTooltip();
    const tip = document.createElement('aside');
    tip.id = HOST_TOOLTIP_ID; tip.className = 'cti-v2-sidebar-tooltip';
    tip.setAttribute('role', 'tooltip'); tip.textContent = value;
    document.body.append(tip);
    const rect = row.getBoundingClientRect();
    const size = tip.getBoundingClientRect();
    tip.style.left = `${Math.max(8, Math.min(innerWidth - size.width - 8, rect.right + 8))}px`;
    tip.style.top = `${Math.max(8, Math.min(innerHeight - size.height - 8, rect.top + 28))}px`;
  }

  function installHostListeners() {
    if (hostListenersInstalled) return;
    hostListenersInstalled = true;
    document.addEventListener('mouseover', hostMouseOver);
    document.addEventListener('mouseout', hostMouseOut);
  }

  function hostMouseOver(event) {
    const row = event.target?.closest?.(`[${HOST_NOTE_ATTR}]`);
    if (row) showHostTooltip(row);
  }

  function hostMouseOut(event) {
    const row = event.target?.closest?.(`[${HOST_NOTE_ATTR}]`);
    if (row && (!event.relatedTarget || !row.contains(event.relatedTarget))) removeHostTooltip();
  }

  function clearHostProjection() {
    document.querySelectorAll(`[${HOST_NOTE_ATTR}]`).forEach(row => row.removeAttribute(HOST_NOTE_ATTR));
    document.querySelectorAll(`[${HOST_CHIP_ATTR}]`).forEach(node => node.remove());
    removeHostTooltip();
  }

  function projectSidebarNotes(payload) {
    const byId = new Map();
    (payload?.summaries || []).forEach(item => {
      const id = String(item?.thread_id || '');
      if (id) byId.set(id, item);
      (item?.thread_keys || []).forEach(key => byId.set(String(key), item));
    });
    document.querySelectorAll('[data-app-action-sidebar-thread-row]').forEach(row => {
      const item = byId.get(String(hostThreadId(row)));
      if (item) row.setAttribute(HOST_NOTE_ATTR, hostSummaryNote(item));
      else row.removeAttribute(HOST_NOTE_ATTR);
    });
  }

  function projectMessageChips(payload) {
    const nodes = hostMessageNodes(), items = hostItems(payload), used = new Set();
    const kept = new Set();
    nodes.forEach((node, index) => {
      const item = hostMatch(node, items, used, index);
      const row = hostActionRow(node);
      if (!item || !row) return;
      const parent = row.parentElement || node;
      let chip = Array.from(parent.children).find(child => child.hasAttribute(HOST_CHIP_ATTR));
      if (!chip) { chip = document.createElement('div'); chip.className = 'cti-v2-message-chip'; chip.setAttribute(HOST_CHIP_ATTR, 'true'); }
      kept.add(chip);
      if (chip.previousElementSibling !== row) row.insertAdjacentElement('afterend', chip);
      chip.textContent = hostChipText(item, index);
      chip.title = hostChipTitle(item);
    });
    document.querySelectorAll(`[${HOST_CHIP_ATTR}]`).forEach(node => { if (!kept.has(node)) node.remove(); });
  }

  function projectHostDetails(payload) {
    installHostListeners();
    if (!payload || !payload.summaries?.length) { clearHostProjection(); return; }
    projectSidebarNotes(payload);
    projectMessageChips(payload);
  }

  function disposeHostDetails() {
    clearHostProjection();
    if (!hostListenersInstalled) return;
    document.removeEventListener('mouseover', hostMouseOver);
    document.removeEventListener('mouseout', hostMouseOut);
    hostListenersInstalled = false;
  }
