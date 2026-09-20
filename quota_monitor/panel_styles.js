  // V2-owned styles: scoped to the panel and companion IDs, with native theme colors.
  function panelCSS() {
    return `
      #codex-context-token-inspector-root {
        --cti-safe:#27b786; --cti-watch:#d69a28; --cti-low:#e05d68;
        position:fixed; z-index:2147483000; box-sizing:border-box;
        width:292px; max-height:calc(100vh - 80px); overflow:auto;
        color:CanvasText; background:color-mix(in srgb,Canvas 94%,transparent);
        border:1px solid color-mix(in srgb,CanvasText 18%,transparent);
        border-radius:14px; box-shadow:0 14px 42px color-mix(in srgb,#000 28%,transparent);
        font:13px/1.45 system-ui,-apple-system,sans-serif; backdrop-filter:blur(16px);
        transition:left .18s ease,top .18s ease,width .18s ease;
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
      #codex-context-token-inspector-root button:focus-visible,
      #codex-context-token-inspector-root select:focus-visible,
      #codex-context-token-inspector-root input:focus-visible,
      #codex-context-token-inspector-mascot:focus-visible { outline:2px solid Highlight; outline-offset:2px; }
      #codex-context-token-inspector-root .cti-header { display:flex; align-items:center; gap:6px; padding:8px; }
      #codex-context-token-inspector-root .cti-title { flex:1; min-width:0; text-align:left; font-weight:700; }
      #codex-context-token-inspector-root .cti-header-actions { display:flex; gap:4px; }
      #codex-context-token-inspector-root .cti-unit-group { display:flex; gap:4px; padding:0 8px 8px; }
      #codex-context-token-inspector-root .cti-unit-group button[data-active="true"],
      #codex-context-token-inspector-root [data-layout-preset][data-active="true"],
      #codex-context-token-inspector-root [data-skin-choice][data-active="true"] { border-color:Highlight; background:color-mix(in srgb,Highlight 18%,Canvas); }
      #codex-context-token-inspector-root .cti-body { padding:0 10px 10px; }
      #codex-context-token-inspector-root .cti-section,
      #codex-context-token-inspector-root details,
      #codex-context-token-inspector-root .cti-settings { margin-top:8px; padding:8px; border-radius:10px; background:color-mix(in srgb,CanvasText 5%,transparent); }
      #codex-context-token-inspector-root summary { cursor:pointer; font-weight:650; }
      #codex-context-token-inspector-root .cti-settings { display:grid; gap:8px; }
      #codex-context-token-inspector-root .cti-settings[hidden] { display:none; }
      #codex-context-token-inspector-root fieldset { border:0; margin:0; padding:0; }
      #codex-context-token-inspector-root legend { margin-bottom:4px; font-weight:650; }
      #codex-context-token-inspector-root .cti-muted { color:color-mix(in srgb,CanvasText 64%,transparent); }
      #codex-context-token-inspector-root .cti-line,
      #codex-context-token-inspector-root .cti-source-row,
      #codex-context-token-inspector-root .cti-update-row { display:flex; align-items:center; justify-content:space-between; gap:8px; }
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
      #codex-context-token-inspector-root .cti-skin-button { display:grid; place-items:center; min-width:0; }
      #codex-context-token-inspector-root .cti-skin-art { width:38px; height:42px; object-fit:contain; }
      #codex-context-token-inspector-root[data-collapsed="true"] .cti-body,
      #codex-context-token-inspector-root[data-collapsed="true"] .cti-unit-group,
      #codex-context-token-inspector-root[data-collapsed="true"] [data-refresh],
      #codex-context-token-inspector-root[data-collapsed="true"] [data-settings-toggle] { display:none; }
      #codex-context-token-inspector-root .cti-mini { display:inline-flex; align-items:center; gap:5px; margin-right:8px; }
      #codex-context-token-inspector-root .cti-mini-copy { display:grid; }
      #codex-context-token-inspector-root .cti-battery { width:7px; height:24px; display:flex; align-items:flex-end; border:1px solid currentColor; border-radius:3px; overflow:hidden; }
      #codex-context-token-inspector-root .cti-battery i { display:block; width:100%; background:currentColor; }
      #codex-context-token-inspector-root [data-resize] { position:absolute; width:14px; height:14px; }
      #codex-context-token-inspector-root [data-resize="nw"] { left:-4px; top:-4px; cursor:nwse-resize; }
      #codex-context-token-inspector-root [data-resize="ne"] { right:-4px; top:-4px; cursor:nesw-resize; }
      #codex-context-token-inspector-root [data-resize="sw"] { left:-4px; bottom:-4px; cursor:nesw-resize; }
      #codex-context-token-inspector-root [data-resize="se"] { right:-4px; bottom:-4px; cursor:nwse-resize; }
      #codex-context-token-inspector-mascot {
        position:fixed; z-index:2147483001; display:none; width:48px; height:52px; padding:0; border:0;
        background:transparent; transform:scale(var(--cti-mascot-scale,1)); transform-origin:top left;
      }
      #codex-context-token-inspector-mascot[data-visible="true"] { display:block; }
      #codex-context-token-inspector-mascot .cti-mascot-art { width:48px; height:52px; object-fit:contain; }
      #codex-context-token-inspector-mascot [data-gauge] { position:absolute; inset:auto 5px -5px; height:8px; display:flex; gap:2px; }
      #codex-context-token-inspector-mascot .cti-gauge-cell { flex:1; display:flex; align-items:flex-end; overflow:hidden; border-radius:2px; background:color-mix(in srgb,CanvasText 12%,transparent); }
      #codex-context-token-inspector-mascot .cti-gauge-cell i { width:100%; background:var(--cti-gauge-color,var(--cti-safe)); }
      #cti-context-hint { position:fixed; z-index:2147483002; max-width:260px; padding:7px 9px; border-radius:8px; color:CanvasText; background:Canvas; box-shadow:0 8px 24px #0004; }
      @media (prefers-reduced-motion:reduce) {
        #codex-context-token-inspector-root { transition:none; }
      }
    `;
  }
