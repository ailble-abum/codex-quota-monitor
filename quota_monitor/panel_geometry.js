  // V2-owned, DOM-light geometry for compact/expanded and edge-docked layouts.
  function hudMode(root) {
    return root.dataset.collapsed === 'true' ? 'compact' : 'expanded';
  }

  function hudBase(root) {
    if (hudMode(root) === 'expanded') return 292;
    // Compact cells are content-sized; reserve only the toggle and cell seams.
    // This keeps one-window accounts narrow without clipping additional windows.
    return Math.max(180, 65 + Math.max(1, root.querySelectorAll('.cti-mini').length) * 70);
  }

  function dockSafeTop() {
    return Math.min(64, Math.max(8, window.innerHeight - 100));
  }

  function dockVerticalY(y, viewportHeight, panelHeight, mascotHeight = 48) {
    const top = Math.min(64, Math.max(8, viewportHeight - 100));
    const bottom = Math.max(top, viewportHeight - Math.max(panelHeight, mascotHeight) - 8);
    return Math.max(top, Math.min(bottom, y));
  }

  function compactDockPanelY(mascotY, mascotHeight, panelHeight) {
    return mascotY + (mascotHeight - panelHeight) / 2;
  }

  function mascotDragGeometry(start, clientY, viewportHeight, panelHeight, mascotHeight = 48) {
    const delta = clientY - start.pointerY;
    const moved = start.moved || Math.abs(delta) >= 4;
    return {moved, y:moved ? dockVerticalY(start.top + delta, viewportHeight, panelHeight, mascotHeight) : start.top};
  }

  function dockCandidate(x, _y, width, _height) {
    if (!edgeDockEnabled()) return null;
    const left = Math.abs(x - 8);
    const right = Math.abs(window.innerWidth - 8 - x - width);
    const distance = Math.min(left, right);
    return distance <= 14 ? (left <= right ? 'left' : 'right') : null;
  }

  function presetWidth(root, preset) {
    const ratio = {mini:0.82, standard:1, large:1.2}[preset] || 1;
    return Math.round(Math.max(180, Math.min(600, hudBase(root) * ratio)));
  }

  function resizeGeometry(start, clientX, clientY, corner, viewportWidth) {
    const horizontal = (clientX - start.x) * (corner.includes('e') ? 1 : -1);
    const vertical = (clientY - start.y) * (corner.includes('s') ? 1 : -1);
    const delta = Math.abs(horizontal) >= Math.abs(vertical) ? horizontal : vertical;
    const room = corner.includes('w') ? start.right - 8 : viewportWidth - start.left - 8;
    const width = Math.max(180, Math.min(600, room, start.width + delta));
    return {left:corner.includes('w') ? start.right - width : start.left, width};
  }

  function contextHintGeometry(anchor, toast, viewport, edge) {
    const beside = edge === 'left' || edge === 'right';
    const left = edge === 'left' ? anchor.right + 8
      : edge === 'right' ? anchor.left - toast.width - 8 : anchor.left;
    const below = anchor.bottom + 8;
    const top = beside ? anchor.top + (anchor.height - toast.height) / 2
      : below + toast.height <= viewport.height - 8 ? below : anchor.top - toast.height - 8;
    return {
      left:Math.round(Math.max(8, Math.min(viewport.width - toast.width - 8, left))),
      top:Math.round(Math.max(68, Math.min(viewport.height - toast.height - 8, top))),
    };
  }
