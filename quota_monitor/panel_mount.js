// V2-owned DOM mounting. Header/CSS are retained, attributed view assets.
  let mountedPanel = null;
  let mountedStyle = null;
  let mountedMascot = null;
  let disposed = false;
  let disposalOK = false;
  let appliedPayload = null;
  function ensureMascot(root) {
    if (disposed) throw new Error('consumer disposed');
    if (mountedMascot) {
      if (!mountedMascot.isConnected || document.getElementById(MASCOT_ID) !== mountedMascot)
        throw new Error('mascot ownership lost');
      return mountedMascot;
    }
    if (document.getElementById(MASCOT_ID)) throw new Error('mascot occupied');
    mountedMascot = createRetainedMascot(root);
    return mountedMascot;
  }
  function positionContextHint(root, toast) {
    if (!disposed && root === mountedPanel) positionRetainedHint(root, toast);
  }
  function disposePanel() {
    if (disposed) return disposalOK;
    disposed = true;
    let ok = true;
    const clean = action => { try { action(); } catch (_) { ok = false; } };
    clean(() => mountedPanel?.__ctiRemoveResize?.());
    clean(() => mountedPanel?.__ctiClearHint?.());
    clean(() => disposeHostDetails());
    clearTimeout(mountedPanel?.__ctiDockHideTimer);
    clearTimeout(mountedMascot?.__ctiPetTimer);
    clearTimeout(mountedMascot?.__ctiReactionTimer);
    for (const node of [mountedPanel, mountedMascot, mountedStyle]) clean(() => node?.remove());
    if (window.__codexContextTokenInspectorUpdate === applyAll)
      clean(() => { if (!Reflect.deleteProperty(window, '__codexContextTokenInspectorUpdate')) ok = false; });
    if (window.__codexContextTokenInspectorPayload === appliedPayload)
      clean(() => { if (!Reflect.deleteProperty(window, '__codexContextTokenInspectorPayload')) ok = false; });
    disposalOK = ok;
    return ok;
  }
  function ensureStyle() {
    if (mountedStyle) {
      const current = document.getElementById(STYLE_ID);
      if (current && current !== mountedStyle) throw new Error('style ownership lost');
      if (!mountedStyle.isConnected) document.head.append(mountedStyle);
      return;
    }
    if (document.getElementById(STYLE_ID)) throw new Error('style occupied');
    const node = document.createElement('style');
    node.id = STYLE_ID;
    node.textContent = panelCSS();
    document.head.append(node);
    mountedStyle = node;
  }
  function ensureHud() {
    if (disposed) throw new Error('consumer disposed');
    if (mountedPanel) {
      if (!mountedPanel.isConnected || document.getElementById(ROOT_ID) !== mountedPanel)
        throw new Error('panel ownership lost');
      return mountedPanel;
    }
    if (document.getElementById(ROOT_ID)) throw new Error('panel occupied');
    const panel = document.createElement('section');
    panel.id = ROOT_ID;
    panel.classList.add('cti-hud');
    panel.dataset.collapsed = 'false';
    try { panel.dataset.collapsed = String(localStorage.getItem(COLLAPSE_KEY) === 'true'); }
    catch (_) { /* Start expanded when the preference cannot be read. */ }
    panel.innerHTML = panelHeader();
    const toggle = () => {
      keepTogglePosition(panel, () => {
        panel.dataset.collapsed = String(panel.dataset.collapsed !== 'true');
        try { localStorage.setItem(COLLAPSE_KEY, panel.dataset.collapsed); }
        catch (_) { /* Keep this mounted panel's choice and finish its layout update. */ }
        panel.querySelector('[data-cti-toggle]').textContent = panel.dataset.collapsed === 'true' ? '+' : '−';
        updateHudTitle(panel);
        clampHud(panel);
      });
      // Restoring a docked layout after a floating compact mode resets visibility.
      // A user-pinned panel must remain accessible after that mode transition.
      if (panel.dataset.docked === 'true' && panel.dataset.dockPinned === 'true') revealDock(panel, true);
    };
    panel.addEventListener('pointerdown', event => {
      if (event.target.closest('[data-cti-unit],[data-cti-title],[data-cti-toggle]')) event.stopPropagation();
    });
    panel.addEventListener('toggle', event => handleDisclosureToggle(panel, event), true);
    panel.addEventListener('input', event => {
      if (event.target.matches('[data-mascot-scale]')) {
        setMascotScalePreference(event.target.valueAsNumber / 100);
        applyStoredHudPosition(panel);
      }
    });
    panel.addEventListener('change', event => {
      if (event.target.matches('[data-alerts]')) {
        try { localStorage.setItem('cti-alerts', String(event.target.checked)); }
        catch (_) { event.target.checked = false; }
      } else if (event.target.matches('[data-edge-dock]')) {
        setEdgeDockEnabled(event.target.checked);
        if (!edgeDockEnabled()) {
          clearDockHide(panel);
          undockHud(panel);
        }
        applyAll(window.__codexContextTokenInspectorPayload);
      } else if (event.target.matches('[data-language]')) {
        setLanguagePreference(event.target.value);
        applyAll(window.__codexContextTokenInspectorPayload);
      } else {
        changeCompanionControl(panel, event.target);
      }
    });
    panel.addEventListener('click', event => {
      const button = event.target.closest('button');
      if (!button || !panel.contains(button)) return;
      if (button.hasAttribute('data-skin-choice')) {
        setMascotSkin(button.dataset.skinChoice);
        applyMascotSkin(panel);
        updateSkinButtons(panel);
        updateMascotSizeControls(panel);
      } else if (button.hasAttribute('data-mascot-scale-auto')) {
        setMascotScalePreference(null);
        applyStoredHudPosition(panel);
      } else if (button.hasAttribute('data-position-reset')) {
        resetPanelPosition(panel);
      } else if (button.hasAttribute('data-layout-preset')) {
        setLayoutPreset(panel, button.dataset.layoutPreset);
      } else if (button.hasAttribute('data-handoff')) {
        void copyHandoff(button);
      } else if (button.hasAttribute('data-refresh')) {
        window.__quotaMonitorV2RefreshRequested = true;
        button.setAttribute('aria-busy', 'true');
        queueMicrotask(() => button.removeAttribute('aria-busy'));
      } else if (button.hasAttribute('data-update-check')) {
        window.__quotaMonitorV2UpdateCheckRequested = true;
        panel.querySelector('[data-update]').dataset.prompt = 'waiting';
        button.disabled = true;
        button.textContent = uiLanguage() === 'zh' ? '检测中…' : 'Checking…';
      } else if (button.hasAttribute('data-update-install')) {
        window.__quotaMonitorV2UpdateInstallRequested = true;
        panel.querySelector('[data-update]').dataset.prompt = 'installing';
        applyAll(window.__codexContextTokenInspectorPayload);
      } else if (button.hasAttribute('data-update-dismiss')) {
        const update = window.__codexContextTokenInspectorPayload?.update;
        const version = update?.status === 'update_available' ? update.latestSemver : null;
        if (/^\d+\.\d+\.\d+$/.test(version || '')) {
          try { localStorage.setItem(UPDATE_DISMISSED_KEY, version); } catch (_) {}
        }
        panel.querySelector('[data-update]').dataset.prompt = '';
        applyAll(window.__codexContextTokenInspectorPayload);
      } else if (button.hasAttribute('data-cti-unit')) {
        event.preventDefault();
        event.stopPropagation();
        setUnitMode(button.dataset.ctiUnit);
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
    document.body.append(panel);
    mountedPanel = panel;
    applyStoredHudPosition(panel);
    installHudDrag(panel);
    updateUnitButtons(panel);
    updateHudLanguage(panel);
    return panel;
  }
