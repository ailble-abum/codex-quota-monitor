  // V2-owned static shell. Dynamic text and state are projected by modules.
  function panelHeader() {
    return `<header class="cti-header">
      <button type="button" class="cti-title" data-cti-title aria-expanded="true">Usage</button>
      <div class="cti-header-actions">
        <button type="button" data-refresh title="Refresh quota">↻</button>
        <button type="button" data-settings-toggle aria-expanded="false" title="Display settings">⚙</button>
        <button type="button" data-cti-toggle aria-label="Collapse monitor">−</button>
      </div>
    </header>
    <div class="cti-unit-group" role="group" aria-label="Token unit">
      <button type="button" data-cti-unit="auto" aria-pressed="false">Auto</button>
      <button type="button" data-cti-unit="raw" aria-pressed="false">Raw</button>
      <button type="button" data-cti-unit="k" aria-pressed="false">K</button>
      <button type="button" data-cti-unit="m" aria-pressed="false">M</button>
    </div>
    <div class="cti-body" data-cti-body></div>`;
  }
