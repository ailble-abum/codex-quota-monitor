  const companionOptions = new Map([
    ['motion', ['cti-companion-motion', '[data-companion-motion]']],
    ['reminders', ['cti-companion-reminders', '[data-companion-reminders]']],
    ['context', ['cti-context-reminders', '[data-context-alerts]']],
  ]);
  const temporaryCompanionOptions = new Map();
  function companionPreference(name) {
    if (!companionOptions.has(name)) return false;
    if (temporaryCompanionOptions.has(name)) return temporaryCompanionOptions.get(name);
    try { return localStorage.getItem(companionOptions.get(name)[0]) !== 'false'; }
    catch (_) { return true; }
  }
  function setCompanionPreference(name, value) {
    if (!companionOptions.has(name) || typeof value !== 'boolean') return false;
    temporaryCompanionOptions.set(name, value);
    try {
      localStorage.setItem(companionOptions.get(name)[0], String(value));
      temporaryCompanionOptions.delete(name);
      return true;
    } catch (_) { return false; }
  }
  function updateCompanionControls(root) {
    for (const [name, [, selector]] of companionOptions) {
      const control = root.querySelector(selector);
      if (control) control.checked = companionPreference(name);
    }
  }
  function changeCompanionControl(root, control) {
    for (const [name, [, selector]] of companionOptions) {
      if (!control.matches(selector)) continue;
      setCompanionPreference(name, control.checked);
      if (!control.checked) root.__ctiClearHint?.();
      applyAll(window.__codexContextTokenInspectorPayload);
      return;
    }
  }
