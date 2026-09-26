  // V2-owned layout state and pointer lifecycle.
  function clearDockHide(root) {
    clearTimeout(root.__ctiDockHideTimer);
    root.__ctiDockHideTimer = null;
  }

  function scheduleDockHide(root) {
    clearDockHide(root);
    if (root.dataset.docked !== 'true' || root.dataset.dockPinned === 'true') return;
    root.__ctiDockHideTimer = setTimeout(() => {
      if (root.dataset.docked !== 'true') return;
      const mascot = document.getElementById(MASCOT_ID);
      const focused = document.activeElement;
      const keyboardFocused = (root.contains(focused) || focused === mascot)
        && focused?.matches?.(':focus-visible');
      if (root.matches(':hover') || mascot?.matches(':hover')
          || keyboardFocused) return;
      root.dataset.revealed = 'false';
      if (root.dataset.collapsed !== 'true') {
        keepTogglePosition(root, () => {
          root.dataset.collapsed = 'true';
          try { localStorage.setItem(COLLAPSE_KEY, 'true'); } catch (_) {}
          const toggle = root.querySelector('[data-cti-toggle]');
          if (toggle) toggle.textContent = '+';
          updateHudTitle(root);
        });
      } else applyStoredHudPosition(root);
    }, 500);
  }

  function revealDock(root, revealed = true) {
    if (root.dataset.docked !== 'true') return;
    clearDockHide(root);
    root.dataset.revealed = String(revealed);
    applyStoredHudPosition(root);
  }

  function undockHud(root) {
    if (!root.__ctiLayout) return;
    const mode = hudMode(root);
    const previous = root.__ctiLayout[mode] || {};
    const rect = root.getBoundingClientRect();
    root.__ctiLayout[mode] = {...previous,
      x:Math.max(8, Math.min(window.innerWidth - rect.width - 8, rect.left)),
      y:Math.max(dockSafeTop(), Math.min(window.innerHeight - rect.height - 8, rect.top))};
    delete root.__ctiLayout[mode].edge;
    for (const key of ['docked', 'dockEdge', 'revealed', 'dockPinned']) delete root.dataset[key];
    const mascot = document.getElementById(MASCOT_ID);
    if (mascot) mascot.dataset.visible = 'false';
    saveLayout(root);
  }

  function applyDockPosition(root, wanted, edge) {
    const mascot = ensureMascot(root);
    const rect = root.getBoundingClientRect();
    const scale = mascotScale();
    const anchorY = Number.isFinite(wanted.y) ? wanted.y : dockSafeTop();
    const mascotHeight = 52 * scale;
    const mascotY = dockVerticalY(anchorY, window.innerHeight, 0, mascotHeight);
    const compact = hudMode(root) === 'compact';
    const panelTargetY = compact ? compactDockPanelY(mascotY, mascotHeight, rect.height) : anchorY;
    // Compact mode centers independently around the retained companion anchor.
    // Its own height alone determines viewport clamping; expanded mode keeps the
    // established top-anchor behavior and companion-aware clamp.
    const panelY = dockVerticalY(panelTargetY, window.innerHeight, rect.height, compact ? 0 : mascotHeight);
    root.dataset.docked = 'true';
    root.dataset.dockEdge = edge;
    root.dataset.revealed ||= 'false';
    mascot.dataset.visible = 'true';
    mascot.dataset.edge = edge;
    if (mascot.dataset.skin !== mascotSkin()) applyMascotSkin(root);
    mascot.style.setProperty('--cti-mascot-scale', String(scale));
    mascot.style.left = edge === 'left' ? '0px' : 'auto';
    mascot.style.right = edge === 'right' ? '0px' : 'auto';
    mascot.style.top = `${mascotY}px`;
    // Leave room for the companion while its redundant gauge retracts whenever
    // either compact or expanded panel content is visible.
    const gap = 60 * scale;
    const visible = root.dataset.revealed === 'true';
    mascot.dataset.panelRevealed = String(visible);
    root.style.left = edge === 'left' ? (visible ? `${gap}px` : `${-rect.width - 2}px`)
      : (visible ? `${window.innerWidth - rect.width - gap}px` : `${window.innerWidth + 2}px`);
    root.style.top = `${panelY}px`;
    positionContextHint(root);
  }

  function applyStoredHudPosition(root) {
    if (root.__ctiGesture) return;
    root.__ctiLayout ||= initialPanelLayout();
    const mode = hudMode(root);
    const wanted = root.__ctiLayout[mode] || root.__ctiLayout.compact || {};
    const base = hudBase(root);
    const docked = edgeDockEnabled() && ['left', 'right'].includes(wanted.edge);
    const available = window.innerWidth - (docked ? 60 * mascotScale() + 8 : 16);
    const width = Math.max(160, Math.min(available, wanted.width || base));
    Object.assign(root.style, {width:`${width}px`, maxHeight:`${Math.max(80, window.innerHeight - 80)}px`, right:'auto', bottom:'auto'});
    root.style.setProperty('--cti-scale', String(Math.max(0.55, Math.min(1.65, width / base))));
    updateMascotSizeControls(root);
    const rect = root.getBoundingClientRect();
    if (docked) return applyDockPosition(root, wanted, wanted.edge);
    if (wanted.edge && root.__ctiLayout[mode]) {
      delete root.__ctiLayout[mode].edge;
      saveLayout(root);
    }
    for (const key of ['docked', 'dockEdge', 'revealed']) delete root.dataset[key];
    const mascot = document.getElementById(MASCOT_ID);
    if (mascot) {
      mascot.dataset.visible = 'false';
      delete mascot.dataset.panelRevealed;
    }
    const x = Number.isFinite(wanted.x) ? wanted.x : 14;
    const y = Number.isFinite(wanted.y) ? wanted.y : window.innerHeight - rect.height - 16;
    root.style.left = `${Math.max(8, Math.min(window.innerWidth - rect.width - 8, x))}px`;
    root.style.top = `${Math.max(dockSafeTop(), Math.min(window.innerHeight - rect.height - 8, y))}px`;
    root.querySelectorAll('[data-resize][role="slider"]').forEach(node => node.setAttribute('aria-valuenow', String(Math.round(width))));
    positionContextHint(root);
  }

  function syncExpandedAnchor(root, x, y) {
    root.__ctiLayout.expanded = {...(root.__ctiLayout.expanded || {}), x, y};
  }

  function setLayoutPreset(root, preset) {
    if (!['mini', 'standard', 'large'].includes(preset)) return;
    setLayoutPreference(preset);
    const mode = hudMode(root);
    const rect = root.getBoundingClientRect();
    const previous = root.__ctiLayout[mode] || {};
    root.__ctiLayout[mode] = {...previous,
      x:Number.isFinite(previous.x) ? previous.x : rect.left,
      y:Number.isFinite(previous.y) ? previous.y : rect.top,
      width:presetWidth(root, preset)};
    saveLayout(root);
    updatePresetButtons(root);
    applyStoredHudPosition(root);
  }

  function installHudDrag(root) {
    if (root.__ctiDragInstalled) return;
    root.__ctiDragInstalled = true;
    root.__ctiApplyPosition = () => applyStoredHudPosition(root);
    root.__ctiRevealDock = () => { root.dataset.dockPinned = 'true'; revealDock(root); };
    const handles = ['nw', 'ne', 'sw', 'se'].map(corner => {
      const node = document.createElement('div');
      node.dataset.resize = corner;
      if (corner === 'se') {
        node.tabIndex = 0; node.setAttribute('role', 'slider');
        node.setAttribute('aria-label', uiLanguage() === 'zh' ? '调整面板大小' : 'Resize panel');
        node.setAttribute('aria-valuemin', '180'); node.setAttribute('aria-valuemax', '600');
        node.setAttribute('aria-valuenow', String(Math.round(root.getBoundingClientRect().width)));
      }
      root.append(node); return node;
    });
    root.addEventListener('pointerenter', () => clearDockHide(root));
    root.addEventListener('pointerleave', () => scheduleDockHide(root));
    root.addEventListener('focusin', () => clearDockHide(root));
    root.addEventListener('focusout', () => scheduleDockHide(root));
    root.addEventListener('keydown', event => {
      if (event.key !== 'Escape' || root.dataset.docked !== 'true') return;
      root.dataset.dockPinned = 'false';
      document.getElementById(MASCOT_ID)?.setAttribute('aria-pressed', 'false');
      revealDock(root, false);
    });
    const persist = (x, y, width, save = true) => {
      const mode = hudMode(root);
      root.__ctiLayout[mode] = {...(root.__ctiLayout[mode] || {}), x, y, ...(width ? {width} : {})};
      if (save) saveLayout(root);
    };
    root.addEventListener('pointerdown', event => {
      if (event.button !== 0) return;
      const resize = event.target.closest('[data-resize]')?.dataset.resize || null;
      const control = event.target.closest('button,input,select,textarea,summary,a,label');
      if (!resize && control && !event.target.closest('[data-cti-title]')) return;
      if (!resize && root.scrollHeight > root.clientHeight && event.clientX >= root.getBoundingClientRect().left + root.clientWidth) return;
      if (!resize && root.dataset.docked === 'true') undockHud(root);
      const rect = root.getBoundingClientRect();
      root.__ctiGesture = {resize, x:event.clientX, y:event.clientY, left:rect.left, top:rect.top, right:rect.right, width:rect.width, moved:false};
      root.setPointerCapture(event.pointerId);
    }, true);
    const move = event => {
      const gesture = root.__ctiGesture;
      if (!gesture) return;
      const dx = event.clientX - gesture.x, dy = event.clientY - gesture.y;
      if (!gesture.moved && Math.abs(dx) + Math.abs(dy) < 4) return;
      gesture.moved = true; event.preventDefault(); root.dataset.dragging = 'true';
      if (gesture.resize) {
        const next = resizeGeometry(gesture, event.clientX, event.clientY, gesture.resize, window.innerWidth);
        persist(next.left, gesture.top, next.width, false);
        root.__ctiGesture = null; applyStoredHudPosition(root); root.__ctiGesture = gesture;
      } else {
        const x = gesture.left + dx, y = gesture.top + dy;
        persist(x, y, null, false);
        root.style.left = `${x}px`; root.style.top = `${y}px`;
        gesture.candidate = dockCandidate(x, y, gesture.width, 0);
        if (gesture.candidate) root.dataset.snapEdge = gesture.candidate; else delete root.dataset.snapEdge;
      }
    };
    const end = event => {
      const gesture = root.__ctiGesture;
      if (!gesture) return;
      root.__ctiGesture = null; delete root.dataset.dragging; delete root.dataset.snapEdge;
      if (gesture.moved) root.__ctiSuppressClickUntil = performance.now() + 400;
      try { root.releasePointerCapture(event.pointerId); } catch (_) {}
      applyStoredHudPosition(root);
      if (gesture.moved) saveLayout(root);
      if (gesture.moved && !gesture.resize && hudMode(root) === 'compact') {
        const rect = root.getBoundingClientRect();
        root.__ctiLayout.compact = {...(root.__ctiLayout.compact || {}), x:rect.left, y:rect.top};
        syncExpandedAnchor(root, rect.left, rect.top); saveLayout(root);
      }
      if (gesture.moved && !gesture.resize && gesture.candidate) {
        const mode = hudMode(root), rect = root.getBoundingClientRect();
        root.__ctiLayout[mode] = {...(root.__ctiLayout[mode] || {}), x:rect.left, y:rect.top, edge:gesture.candidate};
        root.dataset.revealed = 'false'; root.dataset.dockPinned = 'false';
        saveLayout(root); applyStoredHudPosition(root);
      }
    };
    window.addEventListener('pointermove', move, true);
    window.addEventListener('pointerup', end, true);
    window.addEventListener('pointercancel', end, true);
    handles[3].addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
      event.preventDefault(); const rect = root.getBoundingClientRect();
      const delta = ['ArrowLeft', 'ArrowDown'].includes(event.key) ? -12 : 12;
      persist(rect.left, rect.top, Math.max(180, Math.min(600, rect.width + delta)));
      applyStoredHudPosition(root);
    });
    const resize = () => applyStoredHudPosition(root);
    window.addEventListener('resize', resize);
    root.__ctiRemoveResize = () => {
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointermove', move, true);
      window.removeEventListener('pointerup', end, true);
      window.removeEventListener('pointercancel', end, true);
    };
  }

  function keepTogglePosition(root, update) {
    const before = hudMode(root), rect = root.getBoundingClientRect();
    const dockedEdge = root.dataset.docked === 'true' ? root.dataset.dockEdge : null;
    const beforeLayout = root.__ctiLayout[before] || {};
    const mascot = dockedEdge ? document.getElementById(MASCOT_ID) : null;
    const anchorY = dockedEdge
      ? (Number.isFinite(beforeLayout.y) ? beforeLayout.y : mascot?.getBoundingClientRect().top)
      : rect.top;
    root.__ctiLayout[before] = {...beforeLayout, x:rect.left, y:anchorY};
    update();
    const after = hudMode(root);
    root.__ctiLayout[after] = {...(root.__ctiLayout[after] || {}), x:rect.left, y:anchorY};
    if (dockedEdge === 'left' || dockedEdge === 'right') root.__ctiLayout[after].edge = dockedEdge;
    else delete root.__ctiLayout[after].edge;
    saveLayout(root); applyStoredHudPosition(root);
  }

  function clampHud(root) { applyStoredHudPosition(root); }
