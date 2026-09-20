  let temporarySkin = null;
  function registeredSkin(value) {
    return typeof value === 'string' && Object.prototype.hasOwnProperty.call(MASCOT_SKINS, value);
  }
  function mascotSkin() {
    if (temporarySkin !== null) return temporarySkin;
    try {
      const value = localStorage.getItem(SKIN_KEY);
      return registeredSkin(value) ? value : 'cat';
    } catch (_) { return 'cat'; }
  }
  function setMascotSkin(value) {
    if (!registeredSkin(value)) return false;
    temporarySkin = value;
    try {
      localStorage.setItem(SKIN_KEY, value);
      temporarySkin = null;
      return true;
    } catch (_) { return false; }
  }
  function updateSkinButtons(root) {
    const selected = mascotSkin();
    for (const button of root.querySelectorAll('[data-skin-choice]')) {
      const active = String(button.dataset.skinChoice === selected);
      button.dataset.active = active;
      button.setAttribute('aria-pressed', active);
    }
    const label = root.querySelector('[data-skin-current]');
    if (label) label.textContent = MASCOT_SKINS[selected][uiLanguage() === 'zh' ? 'zh' : 'en'];
  }
