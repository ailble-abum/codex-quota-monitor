  // V2-owned styles: scoped to the panel and companion IDs, with native theme colors.
  function panelCSS() {
    return `
      #codex-context-token-inspector-root {
        --cti-safe:#27b786; --cti-watch:#d69a28; --cti-low:#e05d68;
        position:fixed; z-index:2147483000; box-sizing:border-box;
        width:292px; max-height:calc(100vh - 80px); overflow-x:hidden; overflow-y:auto;
        color:CanvasText; background:color-mix(in srgb,Canvas 94%,transparent);
        border:1px solid color-mix(in srgb,CanvasText 18%,transparent);
        border-radius:14px; box-shadow:0 14px 42px color-mix(in srgb,#000 28%,transparent);
        font:13px/1.45 system-ui,-apple-system,sans-serif; backdrop-filter:blur(16px);
        transition:left .18s ease,top .18s ease,width .18s ease,box-shadow .15s ease;
      }
      #codex-context-token-inspector-root[data-dragging="true"] { transition:none; }
      #codex-context-token-inspector-root[data-snap-edge] {
        box-shadow:0 0 0 2px color-mix(in srgb,#4f8cff 78%,transparent),0 12px 36px #0002;
      }
      #codex-context-token-inspector-root, #codex-context-token-inspector-root * { box-sizing:border-box; }
      #codex-context-token-inspector-root button,
      #codex-context-token-inspector-root select,
      #codex-context-token-inspector-root input { font:inherit; color:inherit; }
      #codex-context-token-inspector-root button,
      #codex-context-token-inspector-root select {
        border:1px solid color-mix(in srgb,CanvasText 18%,transparent); border-radius:8px;
        background:color-mix(in srgb,Canvas 88%,CanvasText 12%); padding:4px 7px;
      }
      #codex-context-token-inspector-root button {
        display:inline-grid; place-items:center; width:28px; height:24px;
        border:1px solid transparent; border-radius:6px; background:transparent;
        color:inherit; cursor:pointer; position:relative; z-index:1;
      }
      #codex-context-token-inspector-root button:focus-visible,
      #codex-context-token-inspector-root select:focus-visible,
      #codex-context-token-inspector-root input:focus-visible,
      #codex-context-token-inspector-mascot:focus-visible { outline:2px solid Highlight; outline-offset:2px; }
      #codex-context-token-inspector-root .cti-header {
        display:flex; align-items:center; justify-content:space-between; gap:12px;
        padding:12px 16px; border-bottom:1px solid color-mix(in srgb,CanvasText 7%,transparent);
        font-weight:650; cursor:move; touch-action:none; position:sticky; top:0; z-index:3;
        background:Canvas; zoom:var(--cti-scale,1);
      }
      #codex-context-token-inspector-root .cti-title {
        width:auto; height:auto; display:flex; flex:1; min-width:0; gap:8px;
        text-align:left; font:inherit; font-weight:650; padding:0; background:transparent;
        border:0;
      }
      #codex-context-token-inspector-root [data-cti-title] { cursor:pointer; }
      #codex-context-token-inspector-root [data-cti-title]::before {
        content:''; width:7px; height:7px; flex:none; border-radius:50%; background:var(--cti-tone);
      }
      #codex-context-token-inspector-root .cti-header-actions { display:flex; gap:4px; }
      #codex-context-token-inspector-root .cti-unit-group { display:flex; gap:4px; padding:0 8px 8px; }
      #codex-context-token-inspector-root .cti-unit-group button[data-active="true"],
      #codex-context-token-inspector-root [data-layout-preset][data-active="true"],
      #codex-context-token-inspector-root [data-skin-choice][data-active="true"] { border-color:Highlight; background:color-mix(in srgb,Highlight 18%,Canvas); }
      #codex-context-token-inspector-root .cti-body { padding:0 10px 10px; zoom:var(--cti-scale,1); }
      #codex-context-token-inspector-root .cti-section,
      #codex-context-token-inspector-root details,
      #codex-context-token-inspector-root .cti-settings { margin-top:8px; padding:8px; border-radius:10px; background:color-mix(in srgb,CanvasText 5%,transparent); }
      #codex-context-token-inspector-root summary { cursor:pointer; font-weight:650; }
      #codex-context-token-inspector-root .cti-settings { display:grid; gap:8px; }
      #codex-context-token-inspector-root .cti-settings[hidden] { display:none; }
      /* Header controls are icons; settings controls carry text. */
      #codex-context-token-inspector-root .cti-settings { min-width:0; }
      #codex-context-token-inspector-root .cti-unit-group button,
      #codex-context-token-inspector-root .cti-settings button {
        width:auto; height:auto; min-width:0; min-height:24px; overflow:hidden;
        text-overflow:ellipsis; white-space:nowrap;
      }
      #codex-context-token-inspector-root fieldset { border:0; margin:0; padding:0; }
      #codex-context-token-inspector-root legend { margin-bottom:4px; font-weight:650; }
      #codex-context-token-inspector-root .cti-muted { color:color-mix(in srgb,CanvasText 64%,transparent); }
      #codex-context-token-inspector-root [data-history],
      #codex-context-token-inspector-root [data-explanation] { overflow-wrap:anywhere; }
      #codex-context-token-inspector-root .cti-line,
      #codex-context-token-inspector-root .cti-source-row,
      #codex-context-token-inspector-root .cti-update-row { display:flex; align-items:center; justify-content:space-between; gap:8px; }
      #codex-context-token-inspector-root .cti-update-prompt {
        margin-top:8px; padding:10px; border:1px solid Highlight; border-radius:9px;
        background:color-mix(in srgb,Highlight 10%,Canvas);
      }
      #codex-context-token-inspector-root .cti-update-prompt p { margin:0 0 8px; }
      #codex-context-token-inspector-root .cti-update-prompt button { width:auto; height:auto; margin-right:8px; }
      #codex-context-token-inspector-root .cti-value { font-variant-numeric:tabular-nums; font-weight:700; }
      #codex-context-token-inspector-root .cti-metrics { display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-top:8px; }
      #codex-context-token-inspector-root .cti-metric { display:grid; padding:7px; border-radius:8px; background:color-mix(in srgb,CanvasText 6%,transparent); }
      #codex-context-token-inspector-root .cti-meter { height:7px; overflow:hidden; border-radius:999px; background:color-mix(in srgb,CanvasText 12%,transparent); }
      #codex-context-token-inspector-root .cti-meter > span { display:block; height:100%; background:var(--cti-safe); }
      #codex-context-token-inspector-root [data-tone="watch"] .cti-meter > span,
      #codex-context-token-inspector-root [data-tone="watch"].cti-quota-window .cti-meter > span { background:var(--cti-watch); }
      #codex-context-token-inspector-root [data-tone="low"] .cti-meter > span,
      #codex-context-token-inspector-root [data-tone="low"].cti-quota-window .cti-meter > span { background:var(--cti-low); }
      #codex-context-token-inspector-root .cti-quota-window { margin-top:7px; }
      #codex-context-token-inspector-root .cti-trust,
      #codex-context-token-inspector-root .cti-update-badge,
      #codex-context-token-inspector-root .cti-status { display:inline-block; padding:1px 6px; border-radius:999px; background:color-mix(in srgb,CanvasText 9%,transparent); font-size:11px; }
      #codex-context-token-inspector-root .cti-skin-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:6px; margin-top:7px; }
      #codex-context-token-inspector-root .cti-skin-button { display:grid; place-items:center; width:100%; min-width:0; min-height:64px; padding:3px; }
      #codex-context-token-inspector-root .cti-skin-art { width:38px; height:42px; object-fit:contain; }
      #codex-context-token-inspector-root .cti-skin-button small { min-width:0; max-width:100%; overflow:hidden; text-overflow:ellipsis; }
      #codex-context-token-inspector-root .cti-mascot-size { display:grid; gap:6px; }
      #codex-context-token-inspector-root .cti-mascot-size > .cti-line { flex-wrap:wrap; }
      #codex-context-token-inspector-root [data-mascot-scale-auto] { flex:none; margin-left:auto; }
      #codex-context-token-inspector-root .cti-mascot-size-preview { display:grid; place-items:center; min-height:112px; border:1px solid color-mix(in srgb,CanvasText 15%,transparent); border-radius:8px; }
      #codex-context-token-inspector-root .cti-size-preview-art { display:block; object-fit:contain; }
      #codex-context-token-inspector-root [data-mascot-scale] { appearance:none; -webkit-appearance:none; width:100%; height:28px; margin:0; background:transparent; cursor:pointer; }
      #codex-context-token-inspector-root [data-mascot-scale]::-webkit-slider-runnable-track { height:6px; border-radius:999px; background:color-mix(in srgb,CanvasText 34%,Canvas); }
      #codex-context-token-inspector-root [data-mascot-scale]::-webkit-slider-thumb { appearance:none; -webkit-appearance:none; width:18px; height:18px; margin-top:-6px; border:2px solid Canvas; border-radius:50%; background:var(--cti-safe); }
      #codex-context-token-inspector-root [data-mascot-scale]::-moz-range-track { height:6px; border-radius:999px; background:color-mix(in srgb,CanvasText 34%,Canvas); }
      #codex-context-token-inspector-root [data-mascot-scale]::-moz-range-thumb { width:18px; height:18px; border:2px solid Canvas; border-radius:50%; background:var(--cti-safe); }
      #codex-context-token-inspector-root .cti-mascot-size-limits { font-size:11px; color:color-mix(in srgb,CanvasText 70%,transparent); }
      #codex-context-token-inspector-root[data-collapsed="true"] .cti-body,
      #codex-context-token-inspector-root[data-collapsed="true"] .cti-unit-group,
      #codex-context-token-inspector-root[data-collapsed="true"] [data-refresh],
      #codex-context-token-inspector-root[data-collapsed="true"] [data-settings-toggle] { display:none; }
      #codex-context-token-inspector-root [data-tone="safe"],
      #codex-context-token-inspector-root[data-tone="safe"] { --cti-tone:var(--cti-safe); }
      #codex-context-token-inspector-root [data-tone="watch"],
      #codex-context-token-inspector-root[data-tone="watch"] { --cti-tone:var(--cti-watch); }
      #codex-context-token-inspector-root [data-tone="low"],
      #codex-context-token-inspector-root[data-tone="low"] { --cti-tone:var(--cti-low); }
      #codex-context-token-inspector-root [data-tone="unknown"],
      #codex-context-token-inspector-root[data-tone="unknown"] { --cti-tone:color-mix(in srgb,CanvasText 55%,transparent); }
      #codex-context-token-inspector-root[data-collapsed="true"] { width:max-content; overflow:hidden; }
      #codex-context-token-inspector-root[data-collapsed="true"] .cti-header {
        padding:9px 12px; border:0; gap:10px;
      }
      #codex-context-token-inspector-root[data-collapsed="true"] [data-cti-title]::before { display:none; }
      #codex-context-token-inspector-root .cti-mini {
        display:flex; align-items:center; gap:7px; padding:2px 0;
      }
      #codex-context-token-inspector-root .cti-mini + .cti-mini {
        border-left:1px solid color-mix(in srgb,CanvasText 9%,transparent); padding-left:10px;
      }
      #codex-context-token-inspector-root .cti-battery {
        display:block; position:relative; width:9px; height:30px; flex:none; border-radius:3px;
        background:color-mix(in srgb,var(--cti-tone) 15%,transparent); overflow:hidden;
        box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--cti-tone) 18%,transparent);
      }
      #codex-context-token-inspector-root .cti-battery i {
        position:absolute; bottom:0; left:0; width:100%; min-height:2px;
        background:var(--cti-tone); border-radius:2px;
      }
      #codex-context-token-inspector-root .cti-mini-copy { display:flex; flex-direction:column; gap:3px; }
      #codex-context-token-inspector-root .cti-mini-copy small {
        font:9px/1 system-ui; color:color-mix(in srgb,CanvasText 65%,transparent); white-space:nowrap;
      }
      #codex-context-token-inspector-root .cti-mini-copy strong {
        font:650 14px/1 system-ui; font-variant-numeric:tabular-nums; color:var(--cti-tone);
      }
      #codex-context-token-inspector-root .cti-mini-copy em {
        font:9px/1 system-ui; color:color-mix(in srgb,CanvasText 60%,transparent); white-space:nowrap;
      }
      #codex-context-token-inspector-root [data-resize] {
        position:absolute; width:16px; height:16px; touch-action:none; z-index:5; opacity:0;
        border-radius:4px; background:linear-gradient(135deg,transparent 60%,CanvasText 60%,CanvasText 65%,transparent 65%,transparent 78%,CanvasText 78%,CanvasText 83%,transparent 83%);
      }
      #codex-context-token-inspector-root [data-resize]:hover,
      #codex-context-token-inspector-root [data-resize]:focus-visible { opacity:.8; outline:1px solid currentColor; }
      #codex-context-token-inspector-root [data-resize="nw"] { left:-4px; top:-4px; cursor:nwse-resize; }
      #codex-context-token-inspector-root [data-resize="ne"] { right:-4px; top:-4px; cursor:nesw-resize; }
      #codex-context-token-inspector-root [data-resize="sw"] { left:-4px; bottom:-4px; cursor:nesw-resize; }
      #codex-context-token-inspector-root [data-resize="se"] { right:-4px; bottom:-4px; cursor:nwse-resize; }
      #codex-context-token-inspector-mascot {
        position:fixed; z-index:2147483001; display:none; width:48px; height:52px; padding:0; border:0;
        --cti-safe:#70d4a6; --cti-watch:#8ab5ff; --cti-low:#ff929c;
        background:transparent; transform:scale(var(--cti-mascot-scale,1)); transform-origin:top left;
      }
      #codex-context-token-inspector-mascot[data-visible="true"] { display:block; }
      #codex-context-token-inspector-mascot .cti-mascot-art { width:48px; height:52px; object-fit:contain; }
      #codex-context-token-inspector-mascot:not([data-skin="cat"]) .cti-mascot-art { transition:transform .25s ease,filter .25s ease; }
      #codex-context-token-inspector-mascot:not([data-skin="cat"])[data-expression="happy"] .cti-mascot-art { filter:brightness(1.12) saturate(1.18); }
      #codex-context-token-inspector-mascot:not([data-skin="cat"])[data-expression="concerned"] .cti-mascot-art { filter:saturate(.8); }
      #codex-context-token-inspector-mascot:not([data-skin="cat"])[data-expression="waiting"] .cti-mascot-art { filter:grayscale(.4); }
      #codex-context-token-inspector-mascot:not([data-skin="cat"])[data-expression="notice"] .cti-mascot-art { filter:brightness(1.14); }
      #codex-context-token-inspector-mascot:not([data-skin="cat"])[data-motion="true"][data-expression="pet"] .cti-mascot-art { transform:translateY(-3px) rotate(-5deg); }
      #codex-context-token-inspector-mascot [data-gauge] {
        position:absolute; top:50%; transform:translateY(-50%); display:flex;
        flex-direction:column; gap:4px; width:7px;
      }
      #codex-context-token-inspector-mascot .cti-gauge-cell {
        position:relative; display:block; box-sizing:border-box; width:7px; height:17px;
        border-radius:4px; overflow:hidden; background:color-mix(in srgb,CanvasText 14%,transparent);
        box-shadow:inset 0 0 0 1px color-mix(in srgb,CanvasText 9%,transparent);
      }
      #codex-context-token-inspector-mascot .cti-gauge-cell i {
        position:absolute; left:0; bottom:0; display:block; width:100%;
        background:var(--cti-gauge-color,var(--cti-mascot-accent)); border-radius:3px;
        transition:height .3s ease;
      }
      #codex-context-token-inspector-mascot [data-gauge][data-state="empty"] .cti-gauge-cell {
        background:transparent; box-shadow:none; border:1px dashed color-mix(in srgb,CanvasText 34%,transparent);
      }
      #codex-context-token-inspector-mascot [data-gauge][data-blocked="true"] .cti-gauge-cell {
        background:color-mix(in srgb,var(--cti-low) 16%,transparent);
        box-shadow:inset 0 0 0 1.5px color-mix(in srgb,var(--cti-low) 72%,transparent);
      }
      #codex-context-token-inspector-mascot [data-gauge][data-blocked="true"]::after {
        content:''; position:absolute; left:-2px; right:-2px; top:50%; height:2px;
        margin-top:-1px; border-radius:2px; background:var(--cti-low);
      }
      #codex-context-token-inspector-mascot[data-edge="left"] [data-gauge] { right:-3px; }
      #codex-context-token-inspector-mascot[data-edge="right"] [data-gauge] { left:-3px; }
      #codex-context-token-inspector-mascot[data-art="true"][data-edge="right"] [data-gauge] { left:-10px; }
      #codex-context-token-inspector-mascot[data-art="true"][data-edge="left"] [data-gauge] { right:-10px; }
      #cti-context-hint { position:fixed; z-index:2147483002; max-width:260px; padding:7px 9px; border-radius:8px; color:CanvasText; background:Canvas; box-shadow:0 8px 24px #0004; }
      .cti-v2-sidebar-tooltip {
        position:fixed; z-index:2147483002; max-width:min(26rem,calc(100vw - 1rem));
        padding:.6rem .75rem; border:1px solid color-mix(in srgb,CanvasText 20%,Canvas);
        border-radius:.65rem; background:Canvas; color:CanvasText;
        box-shadow:0 .5rem 1.5rem #0003;
        white-space:pre-wrap; overflow-wrap:anywhere;
        font:13px/1.45 ui-monospace,monospace; pointer-events:none;
      }
      .cti-v2-message-chip {
        display:inline-block; max-width:100%; margin-block-start:.25rem;
        padding:.2rem .45rem; border-radius:.45rem;
        background:color-mix(in srgb,CanvasText 10%,Canvas); color:CanvasText;
        font:600 11px/1.3 system-ui,sans-serif; overflow-wrap:anywhere;
      }
      @media (prefers-reduced-motion:reduce) {
        #codex-context-token-inspector-root { transition:none; }
        #codex-context-token-inspector-mascot .cti-mascot-art { transition:none; transform:none !important; }
      }
    `;
  }
