// V2-owned DOM mounting. Header/CSS are retained, attributed view assets.
  let mountedPanel = null;
  let mountedStyle = null;
  function ensureStyle() {
    if (mountedStyle) return;
    if (document.getElementById(STYLE_ID)) throw new Error('style occupied');
    const node = document.createElement('style');
    node.id = STYLE_ID;
    node.textContent = panelCSS();
    document.head.append(node);
    mountedStyle = node;
  }
  function ensureHud() {
    if (mountedPanel) {
      if (!mountedPanel.isConnected || document.getElementById(ROOT_ID) !== mountedPanel)
        throw new Error('panel ownership lost');
      return mountedPanel;
    }
    if (document.getElementById(ROOT_ID)) throw new Error('panel occupied');
    const panel = document.createElement('section');
    panel.id = ROOT_ID;
    panel.classList.add('cti-hud');
    panel.dataset.collapsed = String(localStorage.getItem(COLLAPSE_KEY) === 'true');
    panel.innerHTML = panelHeader();
    const toggle = () => keepTogglePosition(panel, () => {
      panel.dataset.collapsed = String(panel.dataset.collapsed !== 'true');
      localStorage.setItem(COLLAPSE_KEY, panel.dataset.collapsed);
      panel.querySelector('[data-cti-toggle]').textContent = panel.dataset.collapsed === 'true' ? '+' : '−';
      updateHudTitle(panel);
      clampHud(panel);
    });
    panel.addEventListener('pointerdown', event => {
      if (event.target.closest('[data-cti-unit],[data-cti-title],[data-cti-toggle]')) event.stopPropagation();
    });
    panel.addEventListener('click', event => {
      const button = event.target.closest('button');
      if (!button || !panel.contains(button)) return;
      if (button.hasAttribute('data-cti-unit')) {
        event.preventDefault();
        event.stopPropagation();
        localStorage.setItem(UNIT_KEY, button.dataset.ctiUnit);
        applyAll(window.__codexContextTokenInspectorPayload);
      } else if (button.hasAttribute('data-settings-toggle')) {
        const settings = panel.querySelector('[data-settings]');
        settings.hidden = !settings.hidden;
        button.setAttribute('aria-expanded', String(!settings.hidden));
        clampHud(panel);
      } else if (button.hasAttribute('data-cti-toggle') || button.hasAttribute('data-cti-title')) {
        event.preventDefault();
        event.stopPropagation();
        if (performance.now() < (panel.__ctiSuppressClickUntil || 0) || panel.__ctiSuppressToggle) {
          panel.__ctiSuppressToggle = false;
          return;
        }
        if (button.hasAttribute('data-cti-toggle') || panel.dataset.collapsed === 'true') toggle();
      }
    });
    // V2 has no account-refresh backend yet; do not offer a nonfunctional action.
    panel.querySelector('[data-refresh]').disabled = true;
    document.body.append(panel);
    mountedPanel = panel;
    applyStoredHudPosition(panel);
    installHudDrag(panel);
    updateUnitButtons(panel);
    updateHudLanguage(panel);
    return panel;
  }
