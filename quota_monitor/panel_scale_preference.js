  let temporaryMascotScale;
  function mascotScalePreference() {
    if (temporaryMascotScale !== undefined) return temporaryMascotScale;
    try {
      const value = Number(localStorage.getItem(MASCOT_SCALE_KEY));
      return Number.isFinite(value) && value >= .75 && value <= 2 ? value : null;
    } catch (_) { return null; }
  }
  function setMascotScalePreference(value) {
    if (value !== null && !(typeof value === 'number' && Number.isFinite(value) && value >= .75 && value <= 2)) return false;
    temporaryMascotScale = value;
    try {
      if (value === null) localStorage.removeItem(MASCOT_SCALE_KEY);
      else localStorage.setItem(MASCOT_SCALE_KEY, String(value));
      temporaryMascotScale = undefined;
      return true;
    } catch (_) { return false; }
  }
  function mascotScale() {
    return companionScale(mascotScalePreference(), innerWidth, innerHeight);
  }
  function updateMascotSizeControls(root) {
    const percent = Math.round(mascotScale() * 100);
    const automatic = mascotScalePreference() === null;
    const slider = root.querySelector('[data-mascot-scale]');
    if (slider) slider.value = String(percent);
    const label = root.querySelector('[data-mascot-scale-value]');
    if (label) label.textContent = `${automatic ? (uiLanguage() === 'zh' ? '自动 · ' : 'Auto · ') : ''}${percent}%`;
    root.querySelector('[data-mascot-scale-auto]')?.setAttribute('aria-pressed', String(automatic));
  }
