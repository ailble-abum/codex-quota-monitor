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
  let hostTooltipHideTimer = null;
  let hostSidebarPayload = null;

  function hostLocalSidebarRow(row) {
    return row && !row.closest('[data-app-shell-active-page="false"]') && hostThreadId(row)
      && row.getAttribute('data-app-action-sidebar-thread-kind') === 'local'
      && row.getAttribute('data-app-action-sidebar-thread-host-id') === 'local';
  }

  function hostLoadingNote(row, payload) {
    const zh = uiLanguage() === 'zh';
    if (!payload) {
      return JSON.stringify([[zh ? '用量' : 'Usage',
        zh ? '打开 Codex 聊天查看用量' : 'Open a Codex chat to view usage']]);
    }
    const key = String(hostThreadId(row) || '').replace(/^local:/, '');
    const state = payload?.sidebarStatus;
    const status = state?.threadId === key ? state.status : 'loading';
    const messages = {
      loading: zh ? '正在读取用量…' : 'Reading usage…',
      not_found: zh ? '暂无聊天记录' : 'No chat log',
      ambiguous: zh ? '记录重复，无法读取' : 'Duplicate logs; unavailable',
      unavailable: zh ? '聊天记录暂不可读' : 'Chat log unavailable',
      index_wait: zh ? '正在更新聊天列表…' : 'Updating chat list…',
      incomplete: zh ? '聊天记录仍在读取' : 'Reading chat log',
      ready: zh ? '正在更新用量…' : 'Updating usage…',
    };
    let message = messages[status] || messages.unavailable;
    if (status === 'loading' && state?.threadId === key &&
        Number.isFinite(state.readBytes) && Number.isFinite(state.totalBytes) &&
        state.readBytes >= 0 && state.totalBytes > 0 && state.readBytes <= state.totalBytes) {
      const percent = Math.min(99, Math.floor(100 * state.readBytes / state.totalBytes));
      message = zh ? `正在读取用量 ${percent}%…` : `Reading usage ${percent}%…`;
    }
    return JSON.stringify([[zh ? '用量' : 'Usage', message]]);
  }

  function hostFinite(value) {
    return typeof value === 'number' && Number.isFinite(value);
  }

  function hostText(value) {
    return String(value == null ? '—' : value);
  }

  function hostThreadId(row) {
    const tagged = row.matches('[data-app-action-sidebar-thread-id]')
      ? row : row.querySelector('[data-app-action-sidebar-thread-id]');
    const id = tagged?.dataset.appActionSidebarThreadId || null;
    if (!/^local:client-new-thread:[A-Za-z0-9_-]{1,128}$/.test(id || '')) return id;
    if (tagged.getAttribute('data-app-action-sidebar-thread-active') !== 'true') return null;
    const portals = Array.from(document.querySelectorAll(
      '[data-above-composer-portal][data-above-composer-conversation-id]'))
      .filter(node => !node.closest('[data-app-shell-active-page="false"]'));
    const resolved = portals.length === 1
      ? portals[0].dataset.aboveComposerConversationId.replace(/^local:/, '') : null;
    return /^[A-Za-z0-9_-]{1,128}$/.test(resolved || '') ? resolved : null;
  }

  function hostPercent(value) {
    return hostFinite(value) ? `${Number(value).toFixed(1)}%` : '—';
  }

  function hostNumber(value) {
    return hostFinite(value) ? token(value) : '—';
  }

  function hostSummaryNote(item) {
    const zh = uiLanguage() === 'zh';
    const compactionCount = Number.isSafeInteger(item.compaction_count) && item.compaction_count >= 0
      ? `${item.compaction_count} ${zh ? '次' : item.compaction_count === 1 ? 'time' : 'times'}`
      : zh ? '等待数据…' : 'Waiting for data…';
    const postCompaction = hostFinite(item.post_compaction_percent)
        && item.post_compaction_percent >= 0 && item.post_compaction_percent <= 100
      ? hostPercent(item.post_compaction_percent)
      : item.compaction_count === 0
        ? zh ? '尚未压缩' : 'No compaction yet'
        : hostFinite(item.post_compaction_tokens) && item.post_compaction_tokens >= 0
          ? zh ? '占比未知' : 'Percentage unknown'
          : zh ? '等待下一轮…' : 'Awaiting next turn…';
    return JSON.stringify([
      [zh ? '聊天累计' : 'Chat total', hostNumber(item.session_total_tokens)],
      [zh ? '输入' : 'Input', hostNumber(item.session_input_tokens)],
      [zh ? '缓存输入' : 'Cached input', hostNumber(item.session_cached_input_tokens)],
      [zh ? '输出' : 'Output', hostNumber(item.session_output_tokens)],
      [zh ? '推理' : 'Reasoning', hostNumber(item.session_reasoning_tokens)],
      [zh ? '压缩次数' : 'Compactions', compactionCount],
      [zh ? '压缩后首轮' : 'First after compaction', postCompaction],
    ]);
  }

  function hostSummaryRows(value) {
    try {
      const rows = JSON.parse(value);
      if (Array.isArray(rows) && rows.every(row => Array.isArray(row) && row.length === 2)) return rows;
    } catch (_) {}
    return [];
  }

  function positionHostTooltip(row, tip) {
    const rect = row.getBoundingClientRect();
    const size = tip.getBoundingClientRect();
    const viewportWidth = document.documentElement.clientWidth || innerWidth;
    const viewportHeight = document.documentElement.clientHeight || innerHeight;
    const right = rect.right + 8;
    const preferredLeft = right + size.width <= viewportWidth - 8 ? right : rect.left - size.width - 8;
    tip.style.left = `${Math.max(8, Math.min(viewportWidth - size.width - 8, preferredLeft))}px`;
    tip.style.top = `${Math.max(8, Math.min(viewportHeight - size.height - 8, rect.top))}px`;
  }

  function leavingHostTooltip(event) {
    return !event.relatedTarget?.closest?.(`[${HOST_NOTE_ATTR}]`);
  }

  function hostItems(payload) {
    const detail = payload?.detail;
    return detail && Array.isArray(detail.assistantItems) ? detail.assistantItems : [];
  }

  function hostMessageNodes() {
    for (const selector of HOST_MESSAGE_SELECTORS) {
      const found = new Set();
      for (const node of document.querySelectorAll(selector)) {
        const turn = node.closest('[data-content-search-assistant-turn-key], [data-chatgpt-conversation-turn="true"]');
        const target = turn || node;
        if (!target.closest(`#${ROOT_ID}`)) found.add(target);
      }
      if (found.size) return Array.from(found);
    }
    return [];
  }

  function hostActionRow(node) {
    const sent = node.querySelector('[data-assistant-message-sent-time]');
    if (sent?.parentElement) return sent.parentElement;
    return node.querySelector('.turn-action-controls') || null;
  }

  function hostPlainText(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function hostAssignments(nodes, items) {
    const available = items.map((item, index) => ({item, index, prefix: hostPlainText(item?.textPrefix)}));
    const assigned = new Set();
    return nodes.map((node, position) => {
      const body = hostPlainText(node.textContent);
      const match = available.find(entry => entry.prefix && !assigned.has(entry.index) && body.includes(entry.prefix));
      if (match) {
        assigned.add(match.index);
        return match.item;
      }
      return items[Math.max(0, items.length - nodes.length + position)] || null;
    });
  }

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
    clearTimeout(hostTooltipHideTimer);
    hostTooltipHideTimer = null;
    document.getElementById(HOST_TOOLTIP_ID)?.remove();
    try { delete window.__quotaMonitorV2SidebarThread; } catch (_) {}
  }

  function scheduleHostTooltipRemoval() {
    clearTimeout(hostTooltipHideTimer);
    hostTooltipHideTimer = setTimeout(removeHostTooltip, 120);
  }

  function renderHostTooltip(tip, value) {
    const rows = hostSummaryRows(value);
    if (!rows.length) return false;
    tip.replaceChildren();
    for (const [label, amount] of rows) {
      const labelNode = document.createElement('span');
      labelNode.className = 'cti-v2-sidebar-tooltip-label'; labelNode.textContent = label;
      const valueNode = document.createElement('span');
      valueNode.className = 'cti-v2-sidebar-tooltip-value'; valueNode.textContent = amount;
      tip.append(labelNode, valueNode);
    }
    tip.dataset.note = value;
    return true;
  }

  function showHostTooltip(row) {
    const value = row.getAttribute(HOST_NOTE_ATTR);
    if (!value) return;
    removeHostTooltip();
    const tip = document.createElement('aside');
    tip.id = HOST_TOOLTIP_ID; tip.className = 'cti-v2-sidebar-tooltip';
    tip.setAttribute('role', 'tooltip');
    if (!renderHostTooltip(tip, value)) return;
    tip.__ctiHostRow = row;
    window.__quotaMonitorV2SidebarThread = String(hostThreadId(row)).replace(/^local:/, '');
    tip.addEventListener('mouseenter', () => {
      clearTimeout(hostTooltipHideTimer); hostTooltipHideTimer = null;
      if (!row.isConnected || !row.hasAttribute(HOST_NOTE_ATTR)
          || row.closest('[data-app-shell-active-page="false"]')) removeHostTooltip();
    });
    tip.addEventListener('mouseleave', event => { if (leavingHostTooltip(event)) scheduleHostTooltipRemoval(); });
    document.body.append(tip);
    positionHostTooltip(row, tip);
  }

  function installHostListeners() {
    if (hostListenersInstalled) return;
    hostListenersInstalled = true;
    document.addEventListener('mouseover', hostMouseOver);
    document.addEventListener('mouseout', hostMouseOut);
  }

  function hostMouseOver(event) {
    const row = event.target?.closest?.('[data-app-action-sidebar-thread-row]');
    if (!row) return;
    if (!hostLocalSidebarRow(row)) {
      row.removeAttribute(HOST_NOTE_ATTR); removeHostTooltip();
    } else {
      clearTimeout(hostTooltipHideTimer); hostTooltipHideTimer = null;
      if (document.getElementById(HOST_TOOLTIP_ID)?.__ctiHostRow === row) return;
      if (!row.hasAttribute(HOST_NOTE_ATTR)) row.setAttribute(HOST_NOTE_ATTR, hostLoadingNote(row, hostSidebarPayload));
      showHostTooltip(row);
    }
  }

  function hostMouseOut(event) {
    const row = event.target?.closest?.(`[${HOST_NOTE_ATTR}]`);
    if (!row || (event.relatedTarget && row.contains(event.relatedTarget))) return;
    if (event.relatedTarget?.closest?.(`#${HOST_TOOLTIP_ID}`)) return;
    scheduleHostTooltipRemoval();
  }

  function clearHostProjection() {
    hostSidebarPayload = null;
    document.querySelectorAll(`[${HOST_NOTE_ATTR}]`).forEach(row => row.removeAttribute(HOST_NOTE_ATTR));
    document.querySelectorAll(`[${HOST_CHIP_ATTR}]`).forEach(node => node.remove());
    removeHostTooltip();
  }

  function projectSidebarNotes(payload) {
    hostSidebarPayload = payload;
    const hovered = document.getElementById(HOST_TOOLTIP_ID)?.__ctiHostRow;
    const byId = new Map();
    (payload?.summaries || []).forEach(item => {
      const id = String(item?.thread_id || '');
      if (id) byId.set(id, item);
      (item?.thread_keys || []).forEach(key => byId.set(String(key), item));
    });
    document.querySelectorAll('[data-app-action-sidebar-thread-row]').forEach(row => {
      if (!hostLocalSidebarRow(row)) {
        row.removeAttribute(HOST_NOTE_ATTR);
        return;
      }
      const item = byId.get(String(hostThreadId(row)));
      if (item) row.setAttribute(HOST_NOTE_ATTR, hostSummaryNote(item));
      else if (row === hovered) row.setAttribute(HOST_NOTE_ATTR, hostLoadingNote(row, payload));
      else row.removeAttribute(HOST_NOTE_ATTR);
    });
    const tip = document.getElementById(HOST_TOOLTIP_ID);
    const owner = tip?.__ctiHostRow;
    if (!tip) return;
    if (!owner?.isConnected || !owner.hasAttribute(HOST_NOTE_ATTR)
        || owner.closest('[data-app-shell-active-page="false"]')) {
      removeHostTooltip();
    } else if (tip.dataset.note !== owner.getAttribute(HOST_NOTE_ATTR)) {
      const scrollTop = tip.scrollTop;
      renderHostTooltip(tip, owner.getAttribute(HOST_NOTE_ATTR));
      positionHostTooltip(owner, tip);
      tip.scrollTop = scrollTop;
    }
  }

  function projectMessageChips(payload) {
    const nodes = hostMessageNodes();
    const assignments = hostAssignments(nodes, hostItems(payload));
    const kept = new Set();
    nodes.forEach((node, index) => {
      const item = assignments[index];
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
    if (!payload) { clearHostProjection(); return; }
    projectSidebarNotes(payload);
    projectMessageChips(payload.activeThreadId === null ? null : payload);
  }

  function disposeHostDetails() {
    clearHostProjection();
    if (!hostListenersInstalled) return;
    document.removeEventListener('mouseover', hostMouseOver);
    document.removeEventListener('mouseout', hostMouseOut);
    hostListenersInstalled = false;
  }
