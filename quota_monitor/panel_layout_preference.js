  const layoutChoices = ['mini', 'standard', 'large'];
  function layoutPreset() {
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
