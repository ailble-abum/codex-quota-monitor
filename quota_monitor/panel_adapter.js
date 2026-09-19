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
    if (!data || data !== panelData()) {
      data = {activeThreadId: null, selectedThreadId: null, summaries: [],
        detail: null, detailsByThread: {}, observedAt: Date.now() / 1000};
    }
    window.__codexContextTokenInspectorPayload = data;
    applyHud(data);
  }
  ensureDefaultUnit();
  ensureStyle();
  applyAll(null);
  window.__codexContextTokenInspectorUpdate = applyAll;
})
