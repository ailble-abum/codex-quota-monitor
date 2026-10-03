  // Drafts stay in this mount; settings writes require an explicit button click.
  let contextDefaultsDraft = null;
  let contextDefaultsPending = null;
  let contextDefaultsSequence = 0;
  let contextDefaultsValidation = false;
  let contextRestartPending = false;
  let contextRestartPendingAttempt = 0;
  let contextRestartPendingRevision = null;
  let contextRestartDismissedRevision = null;
  function requestContextRestart(root) {
    const payload = window.__codexContextTokenInspectorPayload;
    const state = payload?.contextDefaults;
    if (contextRestartPending || state?.feedback !== 'saved' ||
        !['available', 'failed'].includes(payload?.contextRestart?.status)) return;
    window.__quotaMonitorV2HostRestartRequested = {revision: state.revision};
    contextRestartPending = true;
    contextRestartPendingAttempt = (payload.contextRestart.attempt || 0) + 1;
    contextRestartPendingRevision = state.revision;
    renderContextDefaults(root, payload);
  }
  function contextDefaultsText(zh, en) { return uiLanguage() === 'zh' ? zh : en; }
  function contextDefaultsRequest(root, action) {
    const state = window.__codexContextTokenInspectorPayload?.contextDefaults;
    if (!state || state.status === 'not_applicable' || contextDefaultsPending || state.status === 'busy') return;
    const id = `context-${Date.now()}-${++contextDefaultsSequence}`;
    const request = {id, action};
    if (action !== 'read') {
      if (state.status !== 'ready') return;
      request.revision = state.revision;
      if (action === 'save') {
        const parse = selector => {
          const input = root.querySelector(selector);
          if (!input.validity.valid) return NaN;
          return input.value === '' ? null : input.valueAsNumber;
        };
        request.windowTokens = parse('[data-context-window]');
        request.compactTokens = parse('[data-context-compact]');
        const valid = value => value === null || Number.isInteger(value) && value > 0 && value <= 2147483647;
        if (!valid(request.windowTokens) || !valid(request.compactTokens) ||
            request.windowTokens !== null && request.compactTokens !== null && request.compactTokens >= request.windowTokens) {
          contextDefaultsValidation = true;
          renderContextDefaults(root, window.__codexContextTokenInspectorPayload);
          return;
        }
      }
    } else contextDefaultsDraft = null;
    contextDefaultsValidation = false;
    contextDefaultsPending = id;
    window.__quotaMonitorV2ContextDefaultsRequested = request;
    renderContextDefaults(root, window.__codexContextTokenInspectorPayload);
  }
  function contextDefaultsInput(root) {
    contextDefaultsValidation = false;
    contextDefaultsDraft = {
      window: root.querySelector('[data-context-window]').value,
      compact: root.querySelector('[data-context-compact]').value,
    };
    renderContextDefaults(root, window.__codexContextTokenInspectorPayload);
  }
  function renderContextDefaults(root, payload) {
    const section = root.querySelector('[data-context-defaults]');
    if (!section) return;
    const state = payload.contextDefaults || {status: 'not_configured'};
    const restart = payload.contextRestart || {status: 'unavailable'};
    if (restart.status === 'restarting' || restart.status === 'reopened' && restart.revision === contextRestartPendingRevision ||
        restart.status === 'failed' && restart.attempt >= contextRestartPendingAttempt ||
        state.revision !== contextRestartPendingRevision && contextRestartPending) contextRestartPending = false;
    if (state.requestId === contextDefaultsPending && state.status !== 'busy') {
      contextDefaultsPending = null;
      if (state.feedback === 'saved' || state.feedback === 'overridden') contextDefaultsDraft = null;
    }
    const restarting = restart.status === 'restarting' || contextRestartPending;
    const busy = state.status === 'busy' || contextDefaultsPending !== null || restarting;
    const ready = state.status === 'ready';
    const unavailable = ['not_configured', 'not_applicable'].includes(state.status);
    for (const [selector, field, draft] of [
      ['[data-context-window]', 'windowTokens', 'window'],
      ['[data-context-compact]', 'compactTokens', 'compact'],
    ]) {
      const input = root.querySelector(selector);
      const value = contextDefaultsDraft ? contextDefaultsDraft[draft] : ready ? String(state[field] ?? '') : '';
      if (input.value !== value) input.value = value;
      input.disabled = busy || !ready;
    }
    for (const button of section.querySelectorAll('[data-context-default-action]')) {
      button.disabled = busy || unavailable || button.dataset.contextDefaultAction !== 'read' && (!ready || state.feedback === 'conflict');
    }
    section.setAttribute('aria-busy', String(busy));
    section.querySelector('[data-context-default-model]').textContent = state.model
      ? contextDefaultsText('默认模型 · ', 'Default model · ') + state.model : '';
    const text = (zh, en) => contextDefaultsText(zh, en);
    let message = text('展开后读取设置。', 'Open to read settings.');
    if (contextDefaultsValidation) message = text('请输入正整数，压缩阈值需小于容量。', 'Use positive integers and a threshold below the capacity.');
    else if (restarting) message = text('Codex 正在重启，插件会自动连接…', 'Restarting Codex. The monitor will reconnect…');
    else if (busy) message = text('处理中…', 'Working…');
    else if (state.status === 'not_applicable') message = text('请切换到本机 Codex 对话。', 'Switch to a local Codex chat.');
    else if (state.status === 'not_configured') message = text('设置暂不可用。', 'Settings unavailable.');
    else if (state.feedback === 'conflict') message = text('设置已被修改，请刷新后重试。', 'Settings changed. Refresh before retrying.');
    else if (contextDefaultsDraft && ready) message = text('尚未保存。', 'Unsaved changes.');
    else if (restart.status === 'failed' && restart.revision === state.revision) message = text('重启未完成，可重试或稍后手动打开。', 'Restart incomplete. Retry or reopen later.');
    else if (restart.status === 'reopened' && restart.revision === state.revision) message = text('Codex 已重启，插件已连接。', 'Codex restarted. Monitor connected.');
    else if (state.feedback === 'saved') message = text('已保存。重启 Codex 后用于新对话。', 'Saved. Restart Codex to use these defaults for new chats.');
    else if (state.feedback === 'overridden') message = text('已保存，但其他配置覆盖了这些值。', 'Saved, but overridden by other configuration.');
    else if (state.feedback === 'write_unconfirmed') message = text('保存结果未确认，请刷新核对。', 'Save unconfirmed. Refresh to check.');
    else if (state.status === 'unavailable') message = text('读取失败，请重试。', 'Read failed. Try again.');
    else if (ready) message = text('项目或配置档可覆盖这些默认值。', 'Projects or profiles can override these defaults.');
    section.querySelector('[data-context-default-status]').textContent = message;
    const prompt = section.querySelector('[data-context-restart]');
    const canRestart = ['available', 'failed'].includes(restart.status) || restarting;
    prompt.hidden = state.feedback !== 'saved' || !canRestart || contextDefaultsDraft !== null ||
      contextRestartDismissedRevision === state.revision;
    for (const button of prompt.querySelectorAll('button')) button.disabled = busy;
    if (section.open && state.status === 'idle' && !busy) contextDefaultsRequest(root, 'read');
  }
