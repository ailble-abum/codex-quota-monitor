// Independent numeric bridge. Host adapters read identifiers only, never text.
(options => {
    const normalize = value => {
        if (typeof value !== 'string') return null;
        const key = value.replace(/^local:/, '');
        return /^[A-Za-z0-9_-]{1,128}$/.test(key) ? key : null;
    };
    const current = () => {
        if (options.host !== 'codex-sidebar') return normalize(window.__quotaMonitorV2Thread);
        const rows = document.querySelectorAll(
            '[data-app-action-sidebar-thread-row][data-app-action-sidebar-thread-active="true"]');
        if (rows.length !== 1) return null;
        const row = rows[0];
        if (row.getAttribute('data-app-action-sidebar-thread-kind') !== 'local' ||
            row.getAttribute('data-app-action-sidebar-thread-host-id') !== 'local') return null;
        return normalize(row.getAttribute('data-app-action-sidebar-thread-id'));
    };
    if (location.href !== options.expected) return options.action === 'read' ? null : false;
    if (options.action === 'read') return current();
    if (options.action === 'invalidate' || options.action === 'release') {
        const previous = window.__quotaMonitorV2Delivery;
        if (!previous || previous.owner !== options.owner) return true;
        let cleared = false;
        try { cleared = previous.invalidate(); }
        finally {
            if (options.action === 'release') {
                previous.stop();
                if (window.__quotaMonitorV2Delivery === previous) {
                    cleared = Reflect.deleteProperty(window, '__quotaMonitorV2Snapshot') && cleared;
                    Reflect.deleteProperty(window, '__quotaMonitorV2Delivery');
                }
            }
        }
        if (!cleared) throw new Error('panel consumer unavailable');
        return true;
    }
    if (!options.key || current() !== options.key) return false;

    const previous = window.__quotaMonitorV2Delivery;
    const deadline = performance.now() + 120000;
    let valid = true;
    const snapshot = () => {
        try {
            valid = valid && location.href === options.expected && current() === options.key &&
                performance.now() < deadline;
        } catch (_) { valid = false; }
        return valid ? options.payload : null;
    };
    Object.defineProperty(window, '__quotaMonitorV2Snapshot', {
        configurable: true, get: snapshot
    });
    if (!options.panel) {
        if (previous) { previous.invalidate(); previous.stop(); }
        window.__quotaMonitorV2Delivery = {
            owner: options.owner, stop: () => {}, invalidate: () => { valid = false; return true; }
        };
        return true;
    }

    let timer;
    let last;
    let lastConsumer;
    const stop = () => clearInterval(timer);
    const empty = () => ({activeThreadId: null, selectedThreadId: null,
        summaries: [], detail: null, detailsByThread: {}, observedAt: Date.now() / 1000});
    const refresh = () => {
        try {
            const data = snapshot();
            const consumer = window.__codexContextTokenInspectorUpdate;
            if (typeof consumer !== 'function') throw new Error('panel consumer unavailable');
            if (data !== last || consumer !== lastConsumer) {
                consumer(data || empty());
                last = data;
                lastConsumer = consumer;
            }
            if (!data) stop();
            return true;
        } catch (_) {
            valid = false;
            stop();
            // Clear through the last working consumer if a replacement hook fails.
            if (lastConsumer) { try { lastConsumer(empty()); } catch (_) {} }
            return false;
        }
    };
    if (!refresh()) throw new Error('panel consumer unavailable');
    timer = setInterval(refresh, 250);
    window.__quotaMonitorV2Delivery = {
        owner: options.owner, stop,
        invalidate: () => { valid = false; return refresh(); }
    };
    if (previous) previous.stop();
    return true;
})
