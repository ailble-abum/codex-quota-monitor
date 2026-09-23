"""Small browser-side probe used by the injector's data refresh loop."""

from __future__ import annotations

from typing import Any


PROBE = r"""
(() => {
  const first = (selectors) => selectors.map((selector) => document.querySelector(selector)).find(Boolean) || null;
  const read = (node, name) => node && node.getAttribute ? node.getAttribute(name) : null;
  const active = first([
    '[data-app-action-sidebar-thread-row][data-app-action-sidebar-thread-active="true"]',
    '[data-app-action-sidebar-thread-row][aria-current="page"]',
    '[data-app-action-sidebar-thread-active="true"]',
    '[data-app-action-sidebar-thread-row][data-app-action-sidebar-thread-active]:not([data-app-action-sidebar-thread-active="false"])'
  ]);
  const activeThreadId = read(active, 'data-app-action-sidebar-thread-id')
    || read(active && active.querySelector('[data-app-action-sidebar-thread-id]'), 'data-app-action-sidebar-thread-id')
    || read(document.querySelector('[data-conversation-id]'), 'data-conversation-id')
    || read(document.querySelector('[data-above-composer-conversation-id]'), 'data-above-composer-conversation-id')
    || null;
  const refresh = window.__ctiRefreshRequested === true;
  const checkUpdate = window.__ctiUpdateCheckRequested === true;
  window.__ctiRefreshRequested = false;
  window.__ctiUpdateCheckRequested = false;
  const rows = document.querySelectorAll('[data-app-action-sidebar-thread-row]').length;
  return {
    href: location.href,
    title: document.title,
    activeThreadId,
    dom: {sidebarRows: rows, activeRow: Boolean(active), conversationId: Boolean(activeThreadId)},
    refresh,
    checkUpdate,
    alerts: localStorage.getItem('cti-alerts') === 'true',
    language: String(document.documentElement.lang || navigator.language || 'en').toLowerCase().startsWith('zh') ? 'zh' : 'en'
  };
})()
"""


def read(client: Any) -> dict[str, Any]:
    value = client.evaluate(PROBE)
    return value if isinstance(value, dict) else {}
