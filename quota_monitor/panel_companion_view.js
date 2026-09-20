  // V2-owned companion view assembly; artwork constants retain their own provenance.
  function companionScale(preference, width, height) {
    if (Number.isFinite(preference) && preference >= 0.75 && preference <= 2) return preference;
    return Math.max(1, Math.min(1.5, width / 1440, height / 900));
  }

  function mascotArt(id) {
    return MASCOT_EXPRESSIONS[id]?.idle || MASCOT_ART[id] || '';
  }

  function mascotMarkup(id, className) {
    const source = mascotArt(id);
    return source
      ? `<img class="${className}" src="${source}" alt="" draggable="false">`
      : `<span class="${className}" aria-hidden="true">🐾</span>`;
  }

  function skinButtons() {
    const key = uiLanguage() === 'zh' ? 'zh' : 'en';
    return Object.entries(MASCOT_SKINS).map(([id, skin]) => {
      const label = skin[key];
      return `<button type="button" class="cti-skin-button" data-skin-choice="${id}" aria-label="${label}" title="${label}">${mascotMarkup(id, 'cti-skin-art')}<small>${label}</small></button>`;
    }).join('');
  }

  function applyMascotSkin(root) {
    const mascot = ensureMascot(root);
    const id = mascotSkin();
    const skin = MASCOT_SKINS[id];
    mascot.innerHTML = mascotMarkup(id, 'cti-mascot-art');
    mascot.dataset.skin = id;
    mascot.dataset.art = String(Boolean(mascotArt(id)));
    mascot.style.setProperty('--cti-mascot-accent', skin.accent);
    const [x, y, size] = skin.ring;
    mascot.style.setProperty('--cti-ring-left', `${x - size / 2}px`);
    mascot.style.setProperty('--cti-ring-top', `${y - size / 2}px`);
    mascot.style.setProperty('--cti-ring-size', `${size}px`);
    mascot.dataset.skinLabel = `${skin[uiLanguage() === 'zh' ? 'zh' : 'en']} · ${uiLanguage() === 'zh' ? '上下拖动调整位置，点击保持展开' : 'Drag vertically to move; click to pin'}`;
    const image = mascot.querySelector('img');
    if (image?.complete) queueMicrotask(() => positionContextHint(root));
    else image?.addEventListener('load', () => positionContextHint(root), {once:true});
    applyMascotContext(root, root.__ctiContext);
    applyCompanionExpression(mascot);
    positionContextHint(root);
  }

  function applyMascotGauge(root) {
    const mascot = document.getElementById(MASCOT_ID);
    if (!mascot) return;
    let gauge = mascot.querySelector('[data-gauge]');
    if (!gauge) {
      gauge = document.createElement('span');
      gauge.dataset.gauge = '';
      gauge.setAttribute('aria-hidden', 'true');
      mascot.append(gauge);
    }
    const {quota, live, windows, blocked} = gaugeReading();
    const readings = windows.length ? windows : [null];
    gauge.dataset.cells = String(readings.length);
    gauge.dataset.state = windows.length ? 'live' : 'empty';
    gauge.dataset.blocked = String(blocked);
    const next = document.createDocumentFragment();
    for (const item of readings) {
      const cell = document.createElement('span');
      cell.className = 'cti-gauge-cell';
      if (item) {
        cell.style.setProperty('--cti-gauge-color', gaugeColor(blocked ? 'low' : quotaTone(item.remaining)));
        if (!blocked) {
          const fill = document.createElement('i');
          fill.style.height = `${Math.max(0, Math.min(100, item.remaining))}%`;
          cell.append(fill);
        }
      }
      next.append(cell);
    }
    gauge.replaceChildren(next);
    const zh = uiLanguage() === 'zh';
    const parts = windows.map(item => `${windowLabel(item, true)} ${Math.round(item.remaining)}%`);
    const context = contextMeterValue(root.__ctiContext);
    if (context !== null) parts.push(`CTX ${Math.round(context)}%`);
    if (!live) parts.push(quota.status === 'loading' ? (zh ? '正在读取配额…' : 'Reading quota…') : (zh ? '配额暂不可用' : 'Quota unavailable'));
    if (blocked) {
      const reset = nearestResetText(windows);
      parts.push(zh ? `已达上限${reset ? `，${reset} 重置` : '，等待重置'}` : `Limit reached${reset ? ` · resets ${reset}` : ''}`);
    }
    const label = [mascot.dataset.skinLabel, parts.join(' · ')].filter(Boolean).join(' · ');
    mascot.setAttribute('aria-label', label);
    mascot.title = label;
  }

  function applyMascotContext(root, used) {
    const mascot = document.getElementById(MASCOT_ID);
    if (!mascot) return;
    let ring = mascot.querySelector('[data-context-ring]');
    if (!ring) {
      ring = document.createElement('span');
      ring.dataset.contextRing = '';
      ring.setAttribute('aria-hidden', 'true');
      mascot.prepend(ring);
    }
    const value = contextMeterValue(used);
    ring.dataset.tone = value === null ? 'unknown' : value >= 85 ? 'high' : value >= 70 ? 'watch' : 'quiet';
    ring.style.setProperty('--cti-context-sweep', `${(value || 0) * 2.7}deg`);
    ring.style.setProperty('--cti-context-color', 'light-dark(#b85b18,#f0a15a)');
    applyMascotGauge(root);
  }
