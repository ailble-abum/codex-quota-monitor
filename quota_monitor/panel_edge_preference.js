  let temporaryEdgeDock;
  function edgeDockEnabled() {
    if (temporaryEdgeDock !== undefined) return temporaryEdgeDock;
    try { return localStorage.getItem(EDGE_DOCK_KEY) !== 'false'; }
    catch (_) { return true; }
  }
  function setEdgeDockEnabled(value) {
    if (typeof value !== 'boolean') return false;
    temporaryEdgeDock = value;
    try {
      localStorage.setItem(EDGE_DOCK_KEY, String(value));
      temporaryEdgeDock = undefined;
      return true;
    } catch (_) { return false; }
  }
