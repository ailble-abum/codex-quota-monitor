// V2-owned renderer shell. Resource markers are filled by the release builder.
(payload => {
  if (document.getElementById('codex-context-token-inspector-root') ||
      document.getElementById('codex-context-token-inspector-style') ||
      document.getElementById('codex-context-token-inspector-mascot'))
    throw new Error('consumer DOM occupied');
  const ROOT_ID = 'codex-context-token-inspector-root';
  const STYLE_ID = 'codex-context-token-inspector-style';
  const COLLAPSE_KEY = 'codex-context-token-inspector-collapsed';
  const POSITION_KEY = 'codex-context-token-inspector-position';
  const UNIT_KEY = 'codex-context-token-inspector-unit';
  const LAYOUT_PRESET_KEY = 'cti-layout-preset';
  const EDGE_DOCK_KEY = 'cti-edge-dock';
  const SKIN_KEY = 'cti-mascot-skin';
  const MASCOT_SCALE_KEY = 'cti-mascot-scale';
  const SKINS_OPEN_KEY = 'cti-skins-open';
  const UPDATE_DISMISSED_KEY = 'cti-update-dismissed-version';
  const MASCOT_ID = 'codex-context-token-inspector-mascot';
  const runtimeChanged = true;
  // Only labels used by the V2 panel live here; host details own their own copy.
  const I18N = {
    en: {monitor:'Usage', tokenUnit:'Token unit', rawUnit:'raw',
      expandMonitor:'Open usage panel', collapseMonitor:'Minimize usage panel',
      refreshQuota:'Refresh quota', displaySettings:'Display settings',
      turn:'Latest request', session:'session', input:'Input', cachedInput:'Cached input',
      output:'Output', noRecords:'No token records found.', unknown:'UNKNOWN',
      high:'HIGH', watch:'WATCH', ok:'OK'},
    zh: {monitor:'用量', tokenUnit:'Token 单位', rawUnit:'原值',
      expandMonitor:'打开用量面板', collapseMonitor:'收起用量面板',
      refreshQuota:'刷新配额', displaySettings:'显示设置',
      turn:'最近请求', session:'会话', input:'输入', cachedInput:'缓存输入',
      output:'输出', noRecords:'暂无 Token 记录。', unknown:'未知',
      high:'高', watch:'注意', ok:'正常'},
  };
  const MASCOT_ART = __COMPANION_ART__;
  const MASCOT_EXPRESSIONS = __COMPANION_EXPRESSIONS__;
  const MASCOT_SKINS = {
    cat:{zh:'星瞳诺瓦',en:'Nova Cat',accent:'#62efc2',ring:[25,25,48]},
    candy:{zh:'软糖女孩',en:'Candy Girl',accent:'#ff9fc5',ring:[15,18,28]},
    corgi:{zh:'柯基助手',en:'Corgi Helper',accent:'#f2ae62',ring:[18,20,34]},
    mint:{zh:'薄荷萌男',en:'Mint Boy',accent:'#70d4a6',ring:[14.5,16,27]},
    frost:{zh:'霜夜先生',en:'Mr. Frost',accent:'#8ab5ff',ring:[15,17,27]},
    tea:{zh:'红茶御姐',en:'Tea Lady',accent:'#c97b88',ring:[17,18,30]},
  };

  function applyHud(payload) {
    const root = ensureHud(), body = root.querySelector('[data-cti-body]');
    if (runtimeChanged) applyMascotSkin(root);
    applyMascotGauge(root);
    if (preparePanelBody(root)) {
      updateMascotSizeControls(root);
      updateSkinButtons(root);
    }
    const quota = payload.quota || {status:'unavailable', windows:[]};
    const {age, live} = accountFreshness(quota);
    const blocked = live && (quota.ordinaryUsageAllowed === false || Boolean(quota.rateLimitReachedType));
    renderAccountOverview(body, quota, live, blocked);
    const id = activeThreadId();
    const fresh = typeof payload.observedAt !== 'number' || Date.now() / 1000 - payload.observedAt < 120;
    const selected = fresh ? (payload.summaries || []).find(item =>
      threadKeys(id).some(key => String(item.thread_id) === key || (item.thread_keys || []).includes(key))) : null;
    root.__ctiSessionTotalTokens = selected?.session_total_tokens;
    root.__ctiContext = selected?.latest_context_percent;
    applyMascotContext(root, root.__ctiContext);
    const health = fresh ? companionHealth(payload, id) : null;
    root.__ctiHealth = health;
    applyCompanionFeedback(root, payload, selected, health, id);
    renderHealth(body, health);
    renderLocalSamples(body, payload.history);
    renderSessionDetails(body, selected);
    renderContext(body, selected);
    renderAccountStatus(body, quota, live, age);
    renderDiagnostics(body, payload);
    updateHudTitle(root);
    updateUnitButtons(root);
    root.querySelector('[data-cti-toggle]').textContent = root.dataset.collapsed === 'true' ? '+' : '−';
    clampHud(root);
  }

  function positionRetainedHint(root, toast = document.getElementById('cti-context-hint')) {
    if (!toast?.isConnected) return;
    const mascot = root.dataset.docked === 'true' ? document.getElementById(MASCOT_ID) : null;
    const edge = mascot?.dataset.visible === 'true' ? root.dataset.dockEdge : null;
    const anchor = (edge ? mascot : root).getBoundingClientRect();
    const placed = contextHintGeometry(anchor, {width:toast.offsetWidth, height:toast.offsetHeight},
      {width:innerWidth, height:innerHeight}, edge);
    toast.style.left = `${placed.left}px`; toast.style.top = `${placed.top}px`;
  }

  function updateHudTitle(root) {
    const title = root.querySelector('[data-cti-title]');
    if (!title) return;
    const collapsed = root.dataset.collapsed === 'true';
    const quota = window.__codexContextTokenInspectorPayload?.quota;
    const {live} = accountFreshness(quota);
    const windows = live ? quota.windows || [] : [];
    const remaining = windows.length ? Math.min(...windows.map(item => item.remaining)) : null;
    const tone = accountTone(quota, remaining, live);
    root.dataset.tone = tone;
    title.setAttribute('aria-expanded', String(!collapsed));
    const compact = windows.map(item => `${windowLabel(item, true)} ${Math.round(item.remaining)}%`).join(' · ');
    const hoverBudget = windows.map(item => {
      const estimate = windowBudgetText(item);
      return `${windowLabel(item, true)} ${estimate || toneLabel(quotaTone(item.remaining))}`;
    }).join(' · ');
    title.title = hoverBudget || toneLabel(tone);
    if (collapsed) {
      const cell = (label, value, cellTone, fill, sub = '', figure = null) =>
        `<span class="cti-mini" data-tone="${cellTone}">${fill == null ? '' : `<span class="cti-battery" aria-hidden="true"><i style="height:${fill}%"></i></span>`}<span class="cti-mini-copy"><small>${label}</small><strong>${figure != null ? figure : value == null ? '—' : Math.round(value) + '%'}</strong>${sub ? `<em>${sub}</em>` : ''}</span></span>`;
      const context = contextMeterValue(root.__ctiContext), health = root.__ctiHealth;
      const sub = health?.count ? `↻${health.count} · ${health.after == null ? '…' : token(health.after)}` : '';
      const chinese = uiLanguage() === 'zh';
      const blocked = live && (quota.ordinaryUsageAllowed === false || Boolean(quota.rateLimitReachedType));
      const html = windows.map(item => cell(windowLabel(item, true), item.remaining,
        blocked ? 'low' : quotaTone(item.remaining), item.remaining, '',
        blocked ? (chinese ? '已停' : 'stopped') : windowBudgetText(item))).join('')
        + cell(chinese ? 'CTX 已用' : 'CTX used', context, contextTone(context), context, sub);
      if (title.innerHTML !== html) title.innerHTML = html;
      const budget = blocked ? (chinese ? '账户已达上限' : 'Account at its limit') : accountBudgetText(quota);
      title.setAttribute('aria-label', [compact, budget, `${chinese ? '上下文已用' : 'Context used'} ${pct(context)}`].filter(Boolean).join(' · '));
    } else if (title.textContent !== tr('monitor')) title.textContent = tr('monitor');
    updateHudLanguage(root);
  }
