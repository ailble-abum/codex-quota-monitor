// Independent adapter inserted beside the retained external view functions.
// The V2 bridge is the sole authority for task identity and snapshot freshness.
  function panelData() {
    try { return window.__quotaMonitorV2Snapshot || null; }
    catch (_) { return null; }
  }
  function activeThreadId() {
    return panelData()?.activeThreadId || null;
  }
  function threadKeys(id) { return id ? [id] : []; }
  function applyAll(data) {
    if (disposed) throw new Error('consumer disposed');
    ensureStyle();
    if (!data || data !== panelData()) {
      data = {activeThreadId: null, selectedThreadId: null, summaries: [],
        detail: null, detailsByThread: {}, health: null, healthThreadId: null, history: null,
        quota: appliedPayload?.quota, build: appliedPayload?.build,
        contextSource: 'unselected', update: {status: 'not_configured'},
        observedAt: Date.now() / 1000};
    }
    appliedPayload = data;
    window.__codexContextTokenInspectorPayload = data;
    applyHud(data);
    projectHostDetails(data);
    // The bridge stops delivering after a thread switch. Account freshness
    // still has its own deadline, even if no subsequent poll reaches the page.
    clearTimeout(accountExpiryTimer);
    accountExpiryTimer = null;
    if (accountFreshness(data.quota).live) {
      const delay = Math.max(1, (data.quota.updatedAt + 120) * 1000 - Date.now());
      accountExpiryTimer = setTimeout(() => {
        if (!disposed) applyAll(panelData());
      }, delay);
    }
  }
  ensureStyle();
  applyAll(null);
  window.__codexContextTokenInspectorUpdate = applyAll;
  return {dispose: disposePanel};
})
