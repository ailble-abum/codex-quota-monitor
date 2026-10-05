  // V2-owned static shell. Dynamic text and state are projected by modules.
  function panelHeader() {
    return `<header class="cti-header">
      <button type="button" class="cti-title" data-cti-title aria-expanded="true">Usage</button>
      <div class="cti-header-actions">
        <button type="button" data-refresh title="Refresh quota"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7v5h-5M20 12a8 8 0 1 0-2.3 5.7M20 12a8 8 0 0 0-2.3-5.7"/></svg></button>
        <button type="button" data-settings-toggle aria-expanded="false" title="Settings"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 3-1 3-3 1-2 5 2 5 3 1 1 3h6l1-3 3-1 2-5-2-5-3-1-1-3Z"/><circle cx="12" cy="12" r="3"/></svg></button>
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
    return `<div data-overview><section class="cti-section" data-quota></section>
      <p class="cti-muted" data-freshness></p>
      <section class="cti-section" data-context></section>
      <section class="cti-section" data-health></section>
      <details data-history-disclosure>
        <summary><span>${text('用量记录', 'Usage history')}</span><span class="cti-summary-meta" data-history-summary></span></summary>
        <section data-history></section>
      </details>
      <details data-details>
        <summary>${text('聊天用量', 'Chat usage')}</summary>
        <div class="cti-metrics" data-metrics></div>
        <p class="cti-muted" data-explanation></p>
      </details>
      </div>
      <div class="cti-settings" data-settings hidden>
        <div class="cti-settings-heading"><strong>${text('设置', 'Settings')}</strong><button type="button" data-settings-back>${text('返回用量', 'Back to usage')}</button></div>
        <section class="cti-settings-group">
          <h3>${text('显示', 'Display')}</h3>
          <div class="cti-setting-row"><span>${text('Token 单位', 'Token unit')}</span><div data-units></div></div>
          <label class="cti-setting-row">${text('语言', 'Language')}
            <select data-language><option value="auto">${text('跟随系统', 'System')}</option><option value="zh">中文</option><option value="en">English</option></select>
          </label>
          <fieldset><legend>${text('面板大小', 'Panel size')}</legend><div class="cti-segmented">
            <button type="button" data-layout-preset="mini" aria-pressed="false">${text('紧凑', 'Compact')}</button>
            <button type="button" data-layout-preset="standard" aria-pressed="false">${text('标准', 'Standard')}</button>
            <button type="button" data-layout-preset="large" aria-pressed="false">${text('大', 'Large')}</button>
          </div></fieldset>
          <label class="cti-check-row"><input type="checkbox" data-edge-dock> ${text('靠边收起', 'Edge docking')}</label>
        </section>
        <details data-context-defaults>
          <summary>${text('默认上下文', 'Context defaults')}</summary>
          <p class="cti-muted">${text('本机 Codex 新对话默认值，ChatGPT 聊天不适用。', 'Defaults for new local Codex chats. Not applicable to ChatGPT chats.')}</p>
          <p class="cti-muted" data-context-default-model></p>
          <label>${text('档位', 'Preset')}
            <select data-context-preset disabled>
              <option value="current">${text('保持当前（默认）', 'Keep current (default)')}</option>
              <option value="everyday">${text('日常任务（256K）', 'Everyday tasks (256K)')}</option>
              <option value="long">${text('长任务（512K）', 'Long tasks (512K)')}</option>
              <option value="extended">${text('超长任务（1M）', 'Extended tasks (1M)')}</option>
              <option value="manual">${text('手动输入', 'Manual')}</option>
            </select>
          </label>
          <p class="cti-muted" data-context-preset-hint></p>
          <p data-context-preset-values></p>
          <div data-context-manual hidden>
            <label>${text('上下文容量（Token）', 'Context capacity (tokens)')}
              <input type="number" min="1" max="2147483647" step="1" data-context-window placeholder="${text('跟随模型', 'Model default')}">
            </label>
            <label>${text('自动压缩阈值（Token）', 'Auto-compact threshold (tokens)')}
              <input type="number" min="1" max="2147483647" step="1" data-context-compact placeholder="${text('跟随模型', 'Model default')}">
            </label>
            <p class="cti-muted">${text('留空跟随模型。', 'Leave blank for model defaults.')}</p>
          </div>
          <p class="cti-muted">${text('容量受模型上限限制，实际压缩可能更早。', 'Model limits apply; compaction may occur earlier.')}</p>
          <div class="cti-context-default-actions">
            <button type="button" data-context-default-action="save" disabled>${text('保存', 'Save')}</button>
            <button type="button" data-context-default-action="reset" disabled>${text('跟随模型', 'Use model defaults')}</button>
            <button type="button" data-context-default-action="read">${text('刷新', 'Refresh')}</button>
          </div>
          <p class="cti-muted" role="status" data-context-default-status></p>
          <div data-context-restart hidden>
            <p>${text('现在重启 Codex？插件会自动连接。', 'Restart Codex now? The monitor will reconnect automatically.')}</p>
            <div class="cti-context-default-actions">
              <button type="button" data-context-restart-now>${text('立即重启', 'Restart now')}</button>
              <button type="button" data-context-restart-later>${text('稍后', 'Later')}</button>
            </div>
          </div>
        </details>
        <details data-companion-settings>
          <summary>${text('伴宠', 'Companion')}<span class="cti-summary-meta" data-skin-current></span></summary>
        <div class="cti-mascot-size">
          <div class="cti-line"><label for="cti-mascot-scale">${text('伴宠大小', 'Companion size')}</label>
            <span data-mascot-scale-value></span>
            <button type="button" data-mascot-scale-auto aria-pressed="false">${text('自动大小', 'Auto size')}</button></div>
          <div class="cti-mascot-size-preview" aria-label="${text('实际大小', 'Actual size')}">${mascotMarkup(mascotSkin(), 'cti-size-preview-art')}</div>
          <input id="cti-mascot-scale" type="range" min="75" max="200" step="5" data-mascot-scale aria-label="${text('伴宠大小', 'Companion size')}">
          <div class="cti-line cti-mascot-size-limits"><span>75%</span><span>200%</span></div>
        </div>
        <details data-skins>
          <summary>${text('选择皮肤', 'Choose skin')}</summary>
          <div class="cti-skin-grid">${skinButtons()}</div>
        </details>
        <label><input type="checkbox" data-companion-motion> ${text('伴宠动效', 'Companion motion')}</label>
        <label><input type="checkbox" data-companion-reminders> ${text('伴宠提醒', 'Companion reminders')}</label>
        </details>
        <details data-reminder-settings>
          <summary>${text('提醒', 'Reminders')}</summary>
        <label><input type="checkbox" data-context-alerts> ${text('上下文提醒', 'Context reminders')}</label>
        <label><input type="checkbox" data-alerts disabled aria-describedby="cti-quota-alerts-unavailable"> ${text('额度通知', 'Quota notifications')}</label>
        <p class="cti-muted" id="cti-quota-alerts-unavailable">${text('通知未启用，需先设置保存位置。', 'Notifications are off. Set a storage location to enable them.')}</p>
        </details>
        <div class="cti-settings-tools">
        <button type="button" data-handoff>${text('复制交接提示', 'Copy handoff prompt')}</button>
        <button type="button" data-position-reset>${text('重置位置', 'Reset position')}</button>
        </div>
        <details class="cti-diagnostics" data-diagnostics-details>
          <summary>${text('版本与连接', 'Version & connection')}</summary>
          <p data-build></p><div data-update></div><p data-dom></p>
        </details>
      </div>`;
  }
