  let transientLanguage = null;
  const languageChoices = ['auto', 'zh', 'en'];
  function languagePreference() {
    if (transientLanguage !== null) return transientLanguage;
    try {
      const value = localStorage.getItem('cti-language');
      return languageChoices.includes(value) ? value : 'auto';
    } catch (_) { return 'auto'; }
  }
  function setLanguagePreference(value) {
    if (!languageChoices.includes(value)) return false;
    transientLanguage = value;
    try {
      localStorage.setItem('cti-language', value);
      transientLanguage = null;
      return true;
    } catch (_) { return false; }
  }
  function uiLanguage() {
    const value = languagePreference();
    if (value !== 'auto') return value;
    const locale = document.documentElement.lang || navigator.language || 'en';
    return locale.toLowerCase().startsWith('zh') ? 'zh' : 'en';
  }
