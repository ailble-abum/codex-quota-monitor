  function renderDiagnostics(body, payload) {
    const zh = uiLanguage() === 'zh';
    const text = (chinese, english) => zh ? chinese : english;
    const write = (selector, value) => {
      const node = body.querySelector(selector);
      if (node && node.textContent !== value) node.textContent = value;
    };
    const build = payload.build || {}, parts = [];
    if (typeof build.pluginVersion === 'string' && build.pluginVersion)
      parts.push(`${text('插件', 'plugin')} ${build.pluginVersion}`);
    if (Number.isSafeInteger(build.runtimeVersion) && build.runtimeVersion >= 0)
      parts.push(`${text('运行时', 'runtime')} ${build.runtimeVersion}`);
    if (Number.isFinite(build.installedAt) && build.installedAt >= 0 && build.installedAt <= 8.64e12)
      parts.push(`${text('安装于', 'installed')} ${new Date(build.installedAt * 1000).toLocaleString(zh ? 'zh-CN' : 'en', {month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})}`);
    write('[data-build]', parts.length ? parts.join(' · ') : text('版本信息未记录', 'Build information not recorded'));

    const current = body.querySelector('[data-update]');
    if (current) {
      const next = current.cloneNode(false), update = payload.update || {status:'not_configured'};
      const version = update.status === 'update_available' ? update.latestSemver : null;
      const root = body.closest('.cti-hud');
      let autoShow = false;
      if (root && /^\d+\.\d+\.\d+$/.test(version || '') && !next.dataset.prompt &&
          root.__ctiAutoUpdate !== version) {
        let dismissed;
        try { dismissed = localStorage.getItem(UPDATE_DISMISSED_KEY); } catch (_) {}
        if (dismissed !== version) {
          root.__ctiAutoUpdate = version;
          next.dataset.prompt = 'show';
          root.dataset.collapsed = 'false';
          body.querySelector('[data-settings]').hidden = false;
          root.querySelector('[data-settings-toggle]').setAttribute('aria-expanded', 'true');
          autoShow = true;
        }
      }
      if (next.dataset.prompt === 'installing' && update.installStatus === 'failed') next.dataset.prompt = 'show';
      if (update.status === 'update_available' && typeof update.latestSemver === 'string' && update.latestSemver) {
        const row = document.createElement('div'); row.className = 'cti-update-row';
        const badge = document.createElement('span'); badge.className = 'cti-update-badge';
        badge.textContent = text('新版本可用', 'Update available');
        const version = document.createElement('strong'); version.textContent = 'v' + update.latestSemver;
        row.append(badge, version);
        try {
          const url = typeof update.url === 'string' ? new URL(update.url) : null;
          if (url?.protocol === 'https:' && !url.username && !url.password) {
            const link = document.createElement('a'); link.className = 'cti-text-button';
            link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
            link.textContent = text('查看', 'View'); row.append(link);
          }
        } catch (_) { /* Keep the version text without an actionable invalid link. */ }
        next.append(row);
      } else if (update.status === 'up_to_date') {
        const label = document.createElement('span'); label.className = 'cti-muted';
        label.textContent = text('已是最新版本', 'Up to date'); next.append(label);
      }
      const check = document.createElement('button');
      check.type = 'button'; check.className = 'cti-text-button'; check.dataset.updateCheck = '';
      check.disabled = update.status === 'checking' || update.status === 'not_configured';
      check.textContent = update.status === 'checking' ? text('检测中…', 'Checking…')
        : text('检测更新', 'Check for updates');
      next.append(check);
      if (next.dataset.prompt === 'waiting' && update.status !== 'checking') {
        if (update.status === 'update_available' || update.status === 'up_to_date' || update.status === 'unavailable')
          next.dataset.prompt = 'show';
      }
      if (next.dataset.prompt === 'waiting' || next.dataset.prompt === 'show' || next.dataset.prompt === 'installing') {
        const prompt = document.createElement('div'); prompt.className = 'cti-update-prompt';
        prompt.setAttribute('role', 'alertdialog');
        prompt.setAttribute('aria-label', text('软件更新', 'Software update'));
        const message = document.createElement('p');
        message.textContent = next.dataset.prompt === 'installing'
          ? text('正在准备更新。安装完成后服务会重启，旧版保留用于回退。', 'Preparing the update. The service will restart; the old version remains for rollback.')
          : update.installStatus === 'failed'
            ? text('自动更新失败，旧版仍可使用。请重试或打开发布页。',
                'Automatic update failed; the previous version is still available. Retry or open the release page.')
          : update.status === 'update_available'
            ? update.installable === true
              ? text(`发现 v${update.latestSemver}。安装会下载并校验正式包，然后重启服务。`,
                  `Version ${update.latestSemver} is available. Installation downloads and verifies the release, then restarts the service.`)
              : text(`发现 v${update.latestSemver}。此安装不能自动替换，请打开发布页安装。`,
                  `Version ${update.latestSemver} is available. Open the release page to install this version.`)
            : update.status === 'up_to_date'
              ? text('已是最新版本。', 'You are up to date.')
              : update.status === 'unavailable'
                ? text('更新检查失败，请稍后再试。', 'Update check failed. Try again later.')
                : text('正在检查更新…', 'Checking for updates…');
        prompt.append(message);
        if (next.dataset.prompt === 'show' && update.status === 'update_available' && update.installable === true) {
          const install = document.createElement('button'); install.type = 'button';
          install.dataset.updateInstall = '';
          install.textContent = text('安装并重启', 'Install and restart'); prompt.append(install);
        }
        if (next.dataset.prompt === 'show' || next.dataset.prompt === 'waiting') {
          const dismiss = document.createElement('button'); dismiss.type = 'button';
          dismiss.dataset.updateDismiss = '';
          dismiss.textContent = text('关闭', 'Close'); prompt.append(dismiss);
        }
        next.append(prompt);
      }
      current.dataset.prompt = next.dataset.prompt || '';
      if (!current.isEqualNode(next)) current.replaceChildren(...next.childNodes);
      if (autoShow) queueMicrotask(() => {
        const prompt = current.querySelector('[role="alertdialog"]');
        if (prompt?.isConnected) prompt.scrollIntoView({block:'nearest'});
      });
    }

    const probe = payload.dom;
    const hasRows = Number.isSafeInteger(probe?.sidebarRows) && probe.sidebarRows >= 0;
    const hasActive = typeof probe?.activeRow === 'boolean';
    const hasId = typeof probe?.conversationId === 'boolean';
    if (!hasRows && !hasActive && !hasId) {
      write('[data-dom]', text('界面探测未提供', 'DOM probe not provided'));
    } else {
      const fields = [];
      if (hasRows) fields.push(`${text('会话', 'threads')} ${probe.sidebarRows}`);
      fields.push(`${text('活动行', 'active')} ${hasActive ? (probe.activeRow ? '✓' : '✗') : '?'}`);
      fields.push(`${text('会话ID', 'id')} ${hasId ? (probe.conversationId ? '✓' : '✗') : '?'}`);
      if (hasRows && (probe.sidebarRows === 0 || (hasActive && !probe.activeRow))) fields.push(text('界面可能已更新', 'UI may have changed'));
      write('[data-dom]', `${text('界面探测', 'DOM probe')} · ${fields.join(' · ')}`);
    }
  }
