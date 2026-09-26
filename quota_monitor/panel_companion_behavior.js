  // V2-owned pure companion behavior. No DOM, storage, timers, or network access.
  function companionExpression(reaction, mood) {
    if (reaction === 'pet') return 'pet';
    if (reaction === 'happy' || reaction === 'hello') return 'happy';
    if (reaction === 'notice') return 'notice';
    if (mood === 'waiting') return 'waiting';
    return mood === 'concerned' ? 'concerned' : 'idle';
  }

  function companionHealth(payload, threadId) {
    const plain = value => String(value || '').replace(/^local:/, '');
    return threadId && plain(threadId) === plain(payload.healthThreadId) ? payload.health || null : null;
  }

  function companionGesture(start, x, y, now) {
    if (start.mode === 'pet') return 'pet';
    if (start.mode === 'drag') return 'drag';
    const distance = Math.hypot(x - start.x, y - start.y);
    if (start.head && distance < 14 && now - start.at >= 350) return 'pet';
    return distance >= 4 ? 'drag' : 'click';
  }

  function companionStep(previous, input, now) {
    const percent = value => Number.isFinite(value) && value >= 0 && value <= 100;
    const level = value => !percent(value) ? null : value <= 0 ? 3 : value <= 10 ? 2 : value <= 20 ? 1 : 0;
    const state = {...previous, windows:{...(previous.windows || {})}, threads:{...(previous.threads || {})}};
    const events = [];
    const sameAccount = Boolean(input.account) && state.account === input.account;
    const previousQuota = state.quotaLast;
    if (input.live) {
      if (state.account !== input.account) state.quotaLast = null;
      state.account = input.account;
    }
    const quotaLevel = !input.live ? null : input.blocked ? 3 : level(input.remaining);
    if (quotaLevel !== null) {
      const windows = input.windows?.length ? input.windows : [{key:'all', resetsAt:input.cycle, remaining:input.remaining}];
      let highest = 0;
      for (const window of windows) {
        const key = JSON.stringify([input.account, window.key, window.resetsAt]);
        const current = level(window.remaining);
        const old = state.windows[key] || {seen:0};
        if (current !== null) {
          if (current > old.seen) highest = Math.max(highest, current);
          state.windows[key] = {seen:Math.max(old.seen, current), at:now};
        }
      }
      if (input.blocked && state.quotaLast !== 3) highest = 3;
      if (highest) events.push(['', 'quota-watch', 'quota-low', 'quota-empty'][highest]);
      else if (sameAccount && previousQuota === 3 && quotaLevel === 0) events.push('quota-restored');
      state.quotaLast = quotaLevel;
      state.windows = Object.fromEntries(Object.entries(state.windows).sort((a,b) => b[1].at - a[1].at).slice(0, 100));
    }
    const contextLevel = !input.thread || !percent(input.ctx) ? 0 : input.ctx >= 95 ? 3 : input.ctx >= 85 ? 2 : input.ctx >= 70 ? 1 : 0;
    if (input.thread) {
      const old = state.threads[input.thread];
      const thread = {...(old || {seen:0, last:0}), at:now};
      if (percent(input.ctx) && input.ctx < 65 && now - thread.last > 1800000) thread.seen = 0;
      if (contextLevel >= 2 && contextLevel > thread.seen) {
        events.push(contextLevel === 3 ? 'ctx-critical' : 'ctx-high');
        thread.seen = contextLevel; thread.last = now;
      }
      if (old && input.compaction && input.compaction !== old.compaction) events.push('compacted');
      thread.compaction = input.compaction || old?.compaction || null;
      state.threads[input.thread] = thread;
      state.threads = Object.fromEntries(Object.entries(state.threads).sort((a,b) => b[1].at - a[1].at).slice(0, 100));
    }
    return {state, quotaLevel, ctxLevel:contextLevel, event:events.length ? events.join('+') : null};
  }
