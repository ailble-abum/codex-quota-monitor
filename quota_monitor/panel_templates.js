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

  function panelBodyTemplate(zh) {
    const text = (chinese, english) => zh ? chinese : english;
    return `<section class="cti-section" data-quota></section>
      <p class="cti-muted" data-freshness></p>
      <section class="cti-section" data-context></section>
      <section class="cti-section" data-health></section>
      <section class="cti-section" data-history></section>
      <details data-details>
        <summary>${text('会话详情', 'Session details')}</summary>
        <div class="cti-metrics" data-metrics></div>
        <p class="cti-muted" data-explanation></p>
      </details>
      <div class="cti-settings" data-settings hidden>
        <div data-units></div>
        <label>${text('语言', 'Language')}
          <select data-language>
            <option value="auto">${text('跟随系统', 'System')}</option>
            <option value="zh">中文</option><option value="en">English</option>
          </select>
        </label>
        <fieldset><legend>${text('面板大小', 'Panel size')}</legend>
          <button type="button" data-layout-preset="mini" aria-pressed="false">${text('紧凑', 'Compact')}</button>
          <button type="button" data-layout-preset="standard" aria-pressed="false">${text('标准', 'Standard')}</button>
          <button type="button" data-layout-preset="large" aria-pressed="false">${text('大', 'Large')}</button>
        </fieldset>
        <label><input type="checkbox" data-edge-dock> ${text('靠边收起', 'Edge docking')}</label>
        <div class="cti-mascot-size">
          <div class="cti-line"><label for="cti-mascot-scale">${text('伴宠大小', 'Companion size')}</label>
            <span data-mascot-scale-value></span>
            <button type="button" data-mascot-scale-auto aria-pressed="false">${text('恢复自动', 'Reset to auto')}</button></div>
          <div class="cti-mascot-size-preview" aria-label="${text('屏幕实际大小预览', 'Actual on-screen size preview')}">${mascotMarkup(mascotSkin(), 'cti-size-preview-art')}</div>
          <input id="cti-mascot-scale" type="range" min="75" max="200" step="5" data-mascot-scale aria-label="${text('伴宠大小', 'Companion size')}">
          <div class="cti-line cti-mascot-size-limits"><span>75%</span><span>200%</span></div>
        </div>
        <details data-skins>
          <summary>${text('伴宠皮肤', 'Companion skin')} · <span data-skin-current></span></summary>
          <div class="cti-skin-grid">${skinButtons()}</div>
        </details>
        <label><input type="checkbox" data-companion-motion> ${text('伴宠动效', 'Companion motion')}</label>
        <label><input type="checkbox" data-companion-reminders> ${text('伴宠提醒', 'Companion reminders')}</label>
        <label><input type="checkbox" data-context-alerts> ${text('上下文提醒', 'Context reminders')}</label>
        <label><input type="checkbox" data-alerts disabled aria-describedby="cti-quota-alerts-unavailable"> ${text('配额通知', 'Quota notifications')}</label>
        <p class="cti-muted" id="cti-quota-alerts-unavailable">${text('配额通知尚未接通。', 'Quota notifications are not connected yet.')}</p>
        <button type="button" data-handoff>${text('复制交接请求', 'Copy handoff request')}</button>
        <button type="button" data-position-reset>${text('重置位置', 'Reset position')}</button>
        <section class="cti-diagnostics">
          <p data-build></p><div data-update></div><p data-dom></p>
        </section>
      </div>`;
  }
