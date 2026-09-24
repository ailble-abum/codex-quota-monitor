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
      if (!current.isEqualNode(next)) current.replaceChildren(...next.childNodes);
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
