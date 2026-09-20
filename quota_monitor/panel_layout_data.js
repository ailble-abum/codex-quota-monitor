  function readLayout() {
    try {
      const saved = JSON.parse(localStorage.getItem('cti-layout-v2') || 'null');
      if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return {};
      const layout = {};
      for (const mode of ['compact', 'expanded']) {
        const value = saved[mode];
        if (!value || typeof value !== 'object' || Array.isArray(value)) continue;
        const entry = {};
        for (const axis of ['x', 'y']) if (Number.isFinite(value[axis])) entry[axis] = value[axis];
        if (Number.isFinite(value.width) && value.width >= 160 && value.width <= 600) entry.width = value.width;
        if (value.edge === 'left' || value.edge === 'right') entry.edge = value.edge;
        if (Object.keys(entry).length) layout[mode] = entry;
      }
      return layout;
    } catch (_) { return {}; }
  }
  function initialPanelLayout() {
    const layout = readLayout();
    if (layout.compact) return layout;
    try {
      const legacy = JSON.parse(localStorage.getItem(POSITION_KEY) || 'null');
      if (!legacy || typeof legacy !== 'object' || Array.isArray(legacy)) return layout;
      const compact = {};
      if (Number.isFinite(legacy.left)) compact.x = legacy.left;
      if (Number.isFinite(legacy.top)) compact.y = legacy.top;
      if (Object.keys(compact).length) layout.compact = compact;
    } catch (_) { /* A missing legacy position does not invalidate the current layout. */ }
    return layout;
  }
