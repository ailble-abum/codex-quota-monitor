  let temporaryLayoutPreset = null;
  const layoutChoices = ['mini', 'standard', 'large'];
  function layoutPreset() {
    if (temporaryLayoutPreset !== null) return temporaryLayoutPreset;
    try {
      const value = localStorage.getItem(LAYOUT_PRESET_KEY);
      return layoutChoices.includes(value) ? value : 'standard';
    } catch (_) { return 'standard'; }
  }
  function updatePresetButtons(root) {
    const value = layoutPreset();
    for (const button of root.querySelectorAll('[data-layout-preset]')) {
      const selected = String(button.dataset.layoutPreset === value);
      button.dataset.active = selected;
      button.setAttribute('aria-pressed', selected);
    }
  }
  function setLayoutPreference(preset) {
    if (!layoutChoices.includes(preset)) return false;
    temporaryLayoutPreset = preset;
    try {
      localStorage.setItem(LAYOUT_PRESET_KEY, preset);
      temporaryLayoutPreset = null;
      return true;
    } catch (_) { return false; }
  }
  function saveLayout(root) {
    try {
      localStorage.setItem('cti-layout-v2', JSON.stringify(root.__ctiLayout));
      return true;
    } catch (_) { return false; }
  }
