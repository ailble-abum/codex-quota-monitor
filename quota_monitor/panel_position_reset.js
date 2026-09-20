  function resetPanelPosition(root) {
    let persisted = true;
    for (const key of [POSITION_KEY, 'cti-layout-v2']) {
      try { localStorage.removeItem(key); }
      catch (_) { persisted = false; }
    }
    clearDockHide(root);
    root.__ctiLayout = {};
    for (const name of ['docked', 'dockEdge', 'dockPinned', 'revealed']) delete root.dataset[name];
    applyStoredHudPosition(root);
    return persisted;
  }
