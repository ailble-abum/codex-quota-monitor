  function renderDiagnostics(body, payload) {
    const zh = uiLanguage() === 'zh';
    const text = (chinese, english) => zh ? chinese : english;
    const write = (selector, value) => {
      const node = body.querySelector(selector);
      if (node && node.textContent !== value) node.textContent = value;
    };
    const build = payload.build || {}, parts = [];
    if (typeof build.pluginVersion === 'string' && build.pluginVersion)
      parts.push(`${text('版本', 'Version')} ${build.pluginVersion}`);
    if (Number.isSafeInteger(build.runtimeVersion) && build.runtimeVersion >= 0)
      parts.push(`${text('组件', 'Component')} ${build.runtimeVersion}`);
    if (Number.isFinite(build.installedAt) && build.installedAt >= 0 && build.installedAt <= 8.64e12)
      parts.push(`${text('安装于', 'installed')} ${new Date(build.installedAt * 1000).toLocaleString(zh ? 'zh-CN' : 'en', {month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})}`);
    write('[data-build]', parts.length ? parts.join(' · ') : text('版本未知', 'Version unknown'));

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
          const overview = body.querySelector('[data-overview]');
          if (overview) overview.hidden = true;
          const diagnostics = body.querySelector('[data-diagnostics-details]');
          if (diagnostics) diagnostics.open = true;
          root.querySelector('[data-settings-toggle]').setAttribute('aria-expanded', 'true');
          autoShow = true;
        }
      }
      if (next.dataset.prompt === 'installing' && update.installStatus === 'failed') next.dataset.prompt = 'show';
      if (update.status === 'update_available' && typeof update.latestSemver === 'string' && update.latestSemver) {
        const row = document.createElement('div'); row.className = 'cti-update-row';
        const badge = document.createElement('span'); badge.className = 'cti-update-badge';
        badge.textContent = text('有新版本', 'Update available');
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
        label.textContent = text('已是最新版', 'Up to date'); next.append(label);
      }
      const check = document.createElement('button');
      check.type = 'button'; check.className = 'cti-text-button'; check.dataset.updateCheck = '';
      check.disabled = update.status === 'checking' || update.status === 'not_configured';
      check.textContent = update.status === 'checking' ? text('检查中…', 'Checking…')
        : text('检查更新', 'Check for updates');
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
          ? text('正在更新，完成后自动恢复。旧版可用于回退。', 'Updating. The monitor will resume automatically; the old version is kept for rollback.')
          : update.installStatus === 'failed'
            ? text('更新失败，旧版仍可用。可重试或手动安装。',
                'Update failed. The old version still works. Retry or install manually.')
          : update.status === 'update_available'
            ? update.installable === true
              ? text(`可更新至 v${update.latestSemver}。更新后会重启额度监控。`,
                  `Update to v${update.latestSemver}. The quota monitor will restart.`)
              : text(`可更新至 v${update.latestSemver}，请到发布页手动安装。`,
                  `Version ${update.latestSemver} is available. Install it from the release page.`)
            : update.status === 'up_to_date'
              ? text('已是最新版。', 'You are up to date.')
              : update.status === 'unavailable'
                ? text('检查失败，稍后重试。', 'Check failed. Try again later.')
                : text('正在检查更新…', 'Checking for updates…');
        prompt.append(message);
        if (next.dataset.prompt === 'show' && update.status === 'update_available' && update.installable === true) {
          const install = document.createElement('button'); install.type = 'button';
          install.dataset.updateInstall = '';
          install.textContent = text('立即更新', 'Update now'); prompt.append(install);
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
      write('[data-dom]', '');
      if (body.querySelector('[data-dom]')) body.querySelector('[data-dom]').title = '';
    } else {
      const fields = [];
      if (hasRows) fields.push(`${text('会话', 'threads')} ${probe.sidebarRows}`);
      fields.push(`${text('当前聊天', 'Current chat')} ${hasActive ? (probe.activeRow ? '✓' : '✗') : '?'}`);
      fields.push(`${text('聊天标识', 'Chat ID')} ${hasId ? (probe.conversationId ? '✓' : '✗') : '?'}`);
      const complete = hasRows && hasActive && hasId;
      const recognized = complete && probe.sidebarRows > 0 && probe.activeRow && probe.conversationId;
      write('[data-dom]', `${text('聊天识别', 'Chat detection')} · ${!complete
        ? text('信息不足', 'Incomplete') : recognized ? text('正常', 'Ready') : text('未识别', 'Not detected')}`);
      if (body.querySelector('[data-dom]')) body.querySelector('[data-dom]').title = fields.join(' · ');
    }
  }
