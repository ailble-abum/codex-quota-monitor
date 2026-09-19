  const disclosureStates = new WeakMap();
  function disclosureKey(node) {
    if (node.matches('details[data-details]')) return 'cti-details-open';
    if (node.matches('details[data-skins]')) return SKINS_OPEN_KEY;
    return null;
  }
  function restoreDisclosures(fragment, previousBody) {
    for (const selector of ['details[data-details]', 'details[data-skins]']) {
      const node = fragment.querySelector(selector);
      const previous = previousBody.querySelector(selector);
      let open = previous?.open || false;
      if (!previous) {
        try { open = localStorage.getItem(disclosureKey(node)) === 'true'; }
        catch (_) { /* Missing storage starts closed. */ }
      }
      disclosureStates.set(node, open);
      node.open = open;
    }
  }
  function handleDisclosureToggle(root, event) {
    const node = event.target;
    if (!root.isConnected || !root.contains(node) || !disclosureStates.has(node)) return;
    if (disclosureStates.get(node) === node.open) return;
    disclosureStates.set(node, node.open);
    try { localStorage.setItem(disclosureKey(node), String(node.open)); }
    catch (_) { /* Keep the current DOM choice for this mounted instance. */ }
    clampHud(root);
  }
