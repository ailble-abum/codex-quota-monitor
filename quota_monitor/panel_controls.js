  // A failed write affects only this mounted instance, never claims persistence.
  let transientUnit = null;
  const unitChoices = ['auto', 'raw', 'k', 'm'];
  function unitMode() {
    if (transientUnit !== null) return transientUnit;
    try {
      const saved = localStorage.getItem(UNIT_KEY);
      return unitChoices.includes(saved) ? saved : 'auto';
    } catch (_) { return 'auto'; }
  }
  function setUnitMode(unit) {
    if (!unitChoices.includes(unit)) return false;
    transientUnit = unit;
    try {
      localStorage.setItem(UNIT_KEY, unit);
      transientUnit = null;
      return true;
    } catch (_) { return false; }
  }

  // V2 control projection; retained preset/skin helpers remain separate.
  function updateUnitButtons(root) {
    const selected = unitMode();
    for (const button of root.querySelectorAll('[data-cti-unit]')) {
      const active = String(button.dataset.ctiUnit === selected);
      button.dataset.active = active;
      button.setAttribute('aria-pressed', active);
    }
    updatePresetButtons(root);
    updateSkinButtons(root);
  }

  function updateHudLanguage(root) {
    const chinese = uiLanguage() === 'zh';
    root.lang = chinese ? 'zh-CN' : 'en';
    const labels = [
      ['.cti-unit-group', tr('tokenUnit')],
      ['[data-cti-toggle]', tr(root.dataset.collapsed === 'true' ? 'expandMonitor' : 'collapseMonitor')],
      ['[data-refresh]', tr('refreshQuota')],
      ['[data-settings-toggle]', tr('displaySettings')],
    ];
    for (const [selector, label] of labels) {
      const control = root.querySelector(selector);
      if (!control) continue;
      control.setAttribute('aria-label', label);
      if (control.matches('[data-refresh],[data-settings-toggle]')) control.title = label;
    }
    for (const [unit, label] of [['auto', chinese ? '自动' : 'Auto'], ['raw', tr('rawUnit')]]) {
      const button = root.querySelector(`[data-cti-unit="${unit}"]`);
      if (button && button.textContent !== label) button.textContent = label;
    }
  }
