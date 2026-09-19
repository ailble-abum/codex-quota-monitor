// V2 owns body replacement; the visual template remains attributed.
  function preparePanelBody(root) {
    const body = root.querySelector('[data-cti-body]');
    const language = uiLanguage();
    if (body.querySelector('[data-quota]') && root.__ctiBodyLanguage === language) return false;
    const units = root.querySelector('.cti-unit-group');
    const settingsOpen = body.querySelector('[data-settings]')?.hidden === false;
    const template = document.createElement('template');
    template.innerHTML = panelBodyTemplate(language === 'zh');
    template.content.querySelector('[data-units]').append(units);
    template.content.querySelector('[data-settings]').hidden = !settingsOpen;
    body.replaceChildren(template.content);
    root.querySelector('[data-settings-toggle]').setAttribute('aria-expanded', String(settingsOpen));
    root.__ctiBodyLanguage = language;
    return true;
  }
