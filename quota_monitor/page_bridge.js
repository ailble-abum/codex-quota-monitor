// Independent numeric bridge. Host adapters read identifiers only, never text.
(options => {
    const normalize = value => {
        if (typeof value !== 'string') return null;
        const key = value.replace(/^local:/, '');
        return /^[A-Za-z0-9_-]{1,128}$/.test(key) ? key : null;
    };
    const current = () => {
        if (options.host !== 'codex-sidebar') return normalize(window.__quotaMonitorV2Thread);
        const rows = Array.from(document.querySelectorAll(
            '[data-app-action-sidebar-thread-row][data-app-action-sidebar-thread-active="true"]'))
            .filter(row => !row.closest('[data-app-shell-active-page="false"]'));
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
        if (previous && previous.owner !== options.owner) return true;
        let cleared = true;
        try { if (previous) cleared = previous.invalidate(); }
        finally {
            if (options.action === 'release') {
                previous?.stop();
                try {
                    const state = window.__quotaMonitorV2Consumer;
                    if (state?.owner === options.owner && typeof state?.dispose === 'function' &&
                        window.__codexContextTokenInspectorUpdate === state.hook) {
                        state.status = 'failed'; // A failed teardown must not be reused as ready.
                        const result = state.dispose();
                        if (result && typeof result.then === 'function') {
                            Promise.resolve(result).catch(() => {});
                            throw new Error('consumer disposal failed');
                        }
                        if (result === false) throw new Error('consumer disposal failed');
                        if (window.__codexContextTokenInspectorUpdate === state.hook &&
                            !Reflect.deleteProperty(window, '__codexContextTokenInspectorUpdate'))
                            throw new Error('consumer disposal failed');
                        if (window.__quotaMonitorV2Consumer === state)
                            Reflect.deleteProperty(window, '__quotaMonitorV2Consumer');
                        cleared = true; // Disposal also handles an unavailable owned view.
                    }
                } finally {
                    if (previous && window.__quotaMonitorV2Delivery === previous) {
                        cleared = Reflect.deleteProperty(window, '__quotaMonitorV2Snapshot') && cleared;
                        Reflect.deleteProperty(window, '__quotaMonitorV2Delivery');
                    }
                }
            }
        }
        if (!cleared) throw new Error('panel consumer unavailable');
        return true;
    }
    if (!options.key || current() !== options.key) return false;

    if (options.action === 'sidebarHover') {
        if (options.host !== 'codex-sidebar') return null;
        const wanted = normalize(window.__quotaMonitorV2SidebarThread);
        if (!wanted) return null;
        const found = Array.from(document.querySelectorAll('[data-app-action-sidebar-thread-row]'))
            .some(row => !row.closest('[data-app-shell-active-page="false"]') &&
                row.getAttribute('data-app-action-sidebar-thread-kind') === 'local' &&
                row.getAttribute('data-app-action-sidebar-thread-host-id') === 'local' &&
                normalize(row.getAttribute('data-app-action-sidebar-thread-id')) === wanted);
        return found ? wanted : null;
    }

    if (options.action === 'refresh') {
        const requested = window.__quotaMonitorV2RefreshRequested === true;
        try { delete window.__quotaMonitorV2RefreshRequested; } catch (_) {}
        return requested;
    }

    if (options.action === 'updateCheck') {
        const requested = window.__quotaMonitorV2UpdateCheckRequested === true;
        try { delete window.__quotaMonitorV2UpdateCheckRequested; } catch (_) {}
        return requested;
    }

    if (options.action === 'updateInstall') {
        const requested = window.__quotaMonitorV2UpdateInstallRequested === true;
        try { delete window.__quotaMonitorV2UpdateInstallRequested; } catch (_) {}
        return requested;
    }

    if (options.action === 'notificationPreference') {
        try { return localStorage.getItem('cti-alerts') === 'true'; }
        catch (_) { return false; }
    }

    if (options.action === 'prepare' || options.action === 'initialize') {
        // A partial/failed initializer must not be retried or adopted as healthy.
        if (window.__quotaMonitorV2Consumer?.status === 'failed')
            throw new Error('consumer initialization failed');
        const hook = window.__codexContextTokenInspectorUpdate;
        if (typeof hook === 'function') return 'ready';
        if (hook != null) throw new Error('consumer hook occupied');
        if (window.__quotaMonitorV2Consumer) throw new Error('consumer hook lost');
        if (options.action === 'prepare') return 'missing';
        const state = {digest: options.consumer.digest, owner: options.owner, status: 'failed'};
        window.__quotaMonitorV2Consumer = state;
        try {
            const initialize = (0, eval)(options.consumer.source);
            if (typeof initialize !== 'function') throw new Error();
            const result = initialize({activeThreadId: null, selectedThreadId: null,
                summaries: [], detail: null, detailsByThread: {}, observedAt: Date.now() / 1000});
            if (result && typeof result.then === 'function') {
                Promise.resolve(result).catch(() => {});
                throw new Error();
            }
            if (typeof window.__codexContextTokenInspectorUpdate !== 'function') throw new Error();
            state.hook = window.__codexContextTokenInspectorUpdate;
            state.dispose = typeof result?.dispose === 'function' ? () => result.dispose() : null;
            state.status = 'ready';
            return 'ready';
        } catch (_) { throw new Error('consumer initialization failed'); }
    }

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
    const managed = window.__quotaMonitorV2Consumer;
    if (managed?.status === 'ready' && managed.hook === lastConsumer) managed.owner = options.owner;
    if (previous) previous.stop();
    return true;
})
