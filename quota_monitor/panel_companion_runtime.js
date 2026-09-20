  // V2-owned companion DOM events, reactions, and local reminder projection.
  function createRetainedMascot(root) {
    const existing = document.getElementById(MASCOT_ID);
    if (existing) return existing;
    const mascot = document.createElement('button');
    mascot.id = MASCOT_ID; mascot.className = 'cti-edge-mascot'; mascot.type = 'button';
    mascot.addEventListener('pointerenter', () => { revealDock(root); companionReact(root, 'hello'); });
    mascot.addEventListener('pointerleave', () => scheduleDockHide(root));
    mascot.addEventListener('focus', () => revealDock(root));
    mascot.addEventListener('blur', () => scheduleDockHide(root));
    mascot.addEventListener('pointerdown', event => {
      if (event.button !== 0 || root.dataset.docked !== 'true') return;
      clearDockHide(root);
      const rect = mascot.getBoundingClientRect();
      mascot.__ctiGesture = {pointerY:event.clientY, top:rect.top, moved:false, x:event.clientX, y:event.clientY,
        at:performance.now(), head:companionPreference('motion') && event.clientY < rect.top + rect.height * 0.6};
      clearTimeout(mascot.__ctiPetTimer);
      mascot.__ctiPetTimer = setTimeout(() => {
        const gesture = mascot.__ctiGesture;
        if (gesture?.head && !gesture.moved) { gesture.mode = 'pet'; companionReact(root, 'pet'); }
      }, 350);
      mascot.setPointerCapture(event.pointerId);
    });
    mascot.addEventListener('pointermove', event => {
      const gesture = mascot.__ctiGesture;
      if (!gesture) return;
      const action = companionGesture(gesture, event.clientX, event.clientY, performance.now());
      if (action === 'pet') { gesture.mode = 'pet'; event.preventDefault(); companionReact(root, 'pet'); return; }
      if (action === 'drag') { gesture.mode = 'drag'; clearTimeout(mascot.__ctiPetTimer); }
      const next = mascotDragGeometry(gesture, event.clientY, window.innerHeight,
        root.getBoundingClientRect().height, 48 * mascotScale());
      if (!next.moved) return;
      gesture.moved = true; event.preventDefault();
      const mode = hudMode(root);
      root.__ctiLayout[mode] = {...(root.__ctiLayout[mode] || {}), y:next.y};
      saveLayout(root); applyStoredHudPosition(root);
    });
    const end = event => {
      const gesture = mascot.__ctiGesture;
      if (!gesture) return;
      mascot.__ctiGesture = null; clearTimeout(mascot.__ctiPetTimer);
      if (gesture.moved) companionReact(root, 'land');
      if (gesture.moved || gesture.mode === 'pet') mascot.__ctiSuppressClickUntil = performance.now() + 400;
      try { mascot.releasePointerCapture(event.pointerId); } catch (_) {}
    };
    mascot.addEventListener('pointerup', end);
    mascot.addEventListener('pointercancel', end);
    mascot.addEventListener('click', event => {
      if (performance.now() < (mascot.__ctiSuppressClickUntil || 0)) { event.preventDefault(); return; }
      companionReact(root, 'hello');
      const pinned = root.dataset.dockPinned !== 'true';
      root.dataset.dockPinned = String(pinned);
      mascot.setAttribute('aria-pressed', String(pinned));
      revealDock(root);
    });
    document.body.append(mascot);
    return mascot;
  }

  function applyCompanionExpression(mascot) {
    const image = mascot.querySelector('img');
    const frames = MASCOT_EXPRESSIONS[mascot.dataset.skin];
    if (!image || !frames) return;
    const expression = companionExpression(mascot.dataset.reaction, mascot.dataset.mood);
    mascot.dataset.expression = expression;
    if (image.getAttribute('src') !== frames[expression]) image.src = frames[expression];
  }

  function companionReact(root, action) {
    const mascot = document.getElementById(MASCOT_ID);
    if (!mascot || !companionPreference('motion') || mascot.dataset.reaction === action) return;
    clearTimeout(mascot.__ctiReactionTimer);
    mascot.dataset.reaction = action;
    applyCompanionExpression(mascot);
    mascot.__ctiReactionTimer = setTimeout(() => {
      delete mascot.dataset.reaction;
      applyCompanionExpression(mascot);
    }, action === 'pet' ? 1400 : 900);
  }

  function applyCompanionFeedback(root, payload, selected, health, threadId) {
    const mascot = document.getElementById(MASCOT_ID);
    if (!mascot) return;
    const {quota, live, windows, blocked} = gaugeReading();
    const remaining = windows.map(item => item.remaining).filter(Number.isFinite);
    const input = {account:quota.accountKey || null, windows, live, blocked,
      remaining:remaining.length ? Math.min(...remaining) : null, thread:threadId || null,
      ctx:selected?.latest_context_percent, compaction:health?.latestAt || null};
    if (!root.__ctiCompanionState) {
      try { root.__ctiCompanionState = JSON.parse(localStorage.getItem('cti-companion-state') || '{}') || {}; }
      catch (_) { root.__ctiCompanionState = {}; }
    }
    const identityChanged = root.__ctiCompanionThread !== threadId || root.__ctiCompanionAccount !== input.account;
    if (identityChanged || !live) {
      root.__ctiClearHint?.(); delete mascot.dataset.reaction; clearTimeout(mascot.__ctiReactionTimer);
    }
    root.__ctiCompanionThread = threadId; root.__ctiCompanionAccount = input.account;
    const result = companionStep(root.__ctiCompanionState, input, Date.now());
    root.__ctiCompanionState = result.state;
    try { localStorage.setItem('cti-companion-state', JSON.stringify(result.state)); } catch (_) {}
    mascot.dataset.motion = String(companionPreference('motion'));
    mascot.dataset.mood = result.quotaLevel === null ? 'unknown' : result.quotaLevel === 3 ? 'waiting'
      : result.quotaLevel >= 1 || result.ctxLevel >= 2 ? 'concerned' : 'idle';
    applyCompanionExpression(mascot);
    let events = (result.event || '').split('+').filter(Boolean);
    if (!companionPreference('context')) events = events.filter(event => !event.startsWith('ctx-') && event !== 'compacted');
    if (!companionPreference('reminders')) events = [];
    if (!events.length) return;
    const zh = uiLanguage() === 'zh';
    const messages = {
      'quota-watch':zh ? '额度剩余不多了，留意可用时长估算。' : 'Quota is getting low. Check the time estimate.',
      'quota-low':zh ? '额度已低于或等于 10%，建议安排好当前步骤。' : 'Quota is at or below 10%. Plan the next step.',
      'quota-empty':zh ? '额度已达上限，等待恢复。' : 'Quota limit reached. Waiting for recovery.',
      'quota-restored':zh ? '已确认额度恢复，可以继续。' : 'Quota recovery confirmed.',
      'ctx-high':zh ? '当前任务上下文偏高，可在阶段结束后整理进度。' : 'This task has high context usage. Consider a handoff.',
      'ctx-critical':zh ? '当前任务上下文接近窗口上限，建议准备接续。' : 'Context is close to the window size. Prepare a handoff.',
      compacted:zh ? '已观察到上下文压缩。' : 'Context compaction observed.',
    };
    let message = events.map(event => messages[event]).join(' ');
    if (events.some(event => event.startsWith('quota-')) && remaining.length) {
      const estimates = windows.map(item => windowBudgetText(item)).filter(Boolean);
      message += estimates.length ? ` ${zh ? '预计可用' : 'Estimated time'} ${estimates.join(' / ')}。`
        : ` ${zh ? '时间估算暂不可用' : 'Time estimate unavailable'}.`;
    }
    if (events.some(event => event.startsWith('ctx-'))) message += ` CTX ${Math.round(input.ctx)}% (${zh ? '最近观测' : 'last observed'})。`;
    if (events.includes('quota-empty')) {
      const reset = nearestResetText(windows); if (reset) message += ` ${zh ? '最近重置' : 'Next reset'} ${reset}`;
    }
    companionReact(root, events.includes('quota-restored') ? 'happy' : events.includes('compacted') ? 'land' : 'notice');
    root.__ctiClearHint?.();
    const toast = document.createElement('aside');
    toast.id = 'cti-context-hint'; toast.setAttribute('role', 'status'); toast.textContent = message;
    document.body.append(toast); positionContextHint(root, toast);
    const timer = setTimeout(() => toast.remove(), 7000);
    root.__ctiClearHint = () => { clearTimeout(timer); toast.remove(); };
  }
