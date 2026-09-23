"""Browser-side host integration kept separate from the custom overlay UI."""

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


# This fragment deliberately owns the selectors, virtualized-message matching,
# and refresh machinery that depend on Codex's renderer.  The injected overlay
# keeps its custom layout, companion, and display code in the injector and only
# calls this small API.  Keeping the boundary in one file makes renderer drift
# visible and independently testable without turning the UI into a framework.
HOST_BRIDGE_SCRIPT = r"""
function createPageBridge(config) {
  const {
    rootId,
    footerAttr,
    chipAttr,
    sidebarHoverAttr,
    originalTitleAttr = 'data-cti-original-title',
    originalTabindexAttr = 'data-cti-original-tabindex',
    hadTabindexAttr = 'data-cti-had-tabindex',
    appliedTabindexAttr = 'data-cti-applied-tabindex',
  } = config;
  const read = (node, name) => node && node.getAttribute ? node.getAttribute(name) : null;
  const sidebarSelector = '[data-app-action-sidebar-thread-row]';

  function rowThreadId(row) {
    return read(row, 'data-app-action-sidebar-thread-id') ||
      read(row && row.querySelector('[data-app-action-sidebar-thread-id]'), 'data-app-action-sidebar-thread-id') ||
      null;
  }
  function activeSidebarRow() {
    return document.querySelector('[data-app-action-sidebar-thread-row][data-app-action-sidebar-thread-active="true"]') ||
      document.querySelector('[data-app-action-sidebar-thread-row][aria-current="page"]') ||
      document.querySelector('[data-app-action-sidebar-thread-active="true"]') ||
      document.querySelector('[data-app-action-sidebar-thread-row][data-app-action-sidebar-thread-active]:not([data-app-action-sidebar-thread-active="false"])');
  }
  function activeThreadId() {
    const row = activeSidebarRow();
    return rowThreadId(row) ||
      read(document.querySelector('[data-conversation-id]'), 'data-conversation-id') ||
      read(document.querySelector('[data-above-composer-conversation-id]'), 'data-above-composer-conversation-id') ||
      null;
  }
  function threadKeys(threadId) {
    const value = String(threadId || '');
    const normalized = value.replace(/^local:/, '');
    return Array.from(new Set([value, normalized, `local:${normalized}`].filter(Boolean)));
  }
  function summaryForActiveThread(summaries) {
    const keys = threadKeys(activeThreadId());
    return (summaries || []).find(item => keys.some(key =>
      String(item.thread_id) === key || (item.thread_keys || []).includes(key))) || null;
  }
  function detailForActiveThread(payload) {
    const details = payload?.detailsByThread || {};
    for (const key of threadKeys(activeThreadId() || payload?.activeThreadId)) {
      if (details[key]) return details[key];
    }
    return null;
  }
  function sidebarRows() {
    return Array.from(document.querySelectorAll(sidebarSelector));
  }
  function cleanOriginalTitle(value) {
    return String(value || '')
      .split(/\n{2,}(?=(?:Context|上下文)\s)/)[0]
      .replace(/\n?(?:Context|上下文)\s+[\s\S]*$/m, '')
      .trim();
  }
  function restoreSidebarRow(row) {
    if (row.hasAttribute(originalTitleAttr)) {
      // A retained virtualized row can receive a fresh native title while the
      // overlay is active.  Keep that newer host value instead of reviving the
      // snapshot taken when this decoration was first applied.
      if (!row.hasAttribute('title')) {
        const title = row.getAttribute(originalTitleAttr) || '';
        if (title) row.setAttribute('title', title); else row.removeAttribute('title');
      }
      row.removeAttribute(originalTitleAttr);
    }
    row.removeAttribute(sidebarHoverAttr);
    if (row.hasAttribute(originalTabindexAttr)) {
      // Restore only the focusability that this bridge added. A different
      // current value belongs to the host and must survive overlay cleanup.
      if (row.getAttribute('tabindex') === row.getAttribute(appliedTabindexAttr)) {
        if (row.getAttribute(hadTabindexAttr) === 'true') {
          row.setAttribute('tabindex', row.getAttribute(originalTabindexAttr) || '');
        } else {
          row.removeAttribute('tabindex');
        }
      }
      row.removeAttribute(originalTabindexAttr);
      row.removeAttribute(hadTabindexAttr);
      row.removeAttribute(appliedTabindexAttr);
    }
  }
  function projectSidebar(summaries, hoverText) {
    const byThread = new Map();
    summaries.forEach(item => {
      byThread.set(String(item.thread_id), item);
      (item.thread_keys || []).forEach(key => byThread.set(String(key), item));
    });
    sidebarRows().forEach(row => {
      const item = byThread.get(String(rowThreadId(row)));
      if (!item) {
        restoreSidebarRow(row);
        return;
      }
      if (!row.hasAttribute(originalTitleAttr) || row.hasAttribute('title')) {
        row.setAttribute(originalTitleAttr, cleanOriginalTitle(row.getAttribute('title') || ''));
      }
      row.removeAttribute('title');
      row.setAttribute(sidebarHoverAttr, hoverText(item));
      if (!row.matches('a,button') && row.tabIndex < 0) {
        if (!row.hasAttribute(originalTabindexAttr)) {
          row.setAttribute(originalTabindexAttr, row.getAttribute('tabindex') || '');
          row.setAttribute(hadTabindexAttr, String(row.hasAttribute('tabindex')));
        } else if (row.getAttribute('tabindex') !== row.getAttribute(appliedTabindexAttr)) {
          row.setAttribute(originalTabindexAttr, row.getAttribute('tabindex') || '');
          row.setAttribute(hadTabindexAttr, String(row.hasAttribute('tabindex')));
        }
        row.tabIndex = 0;
        row.setAttribute(appliedTabindexAttr, '0');
      }
    });
  }
  function clearSidebar() {
    sidebarRows().forEach(restoreSidebarRow);
  }
  function hideSidebarTooltip() {
    const tooltip = document.querySelector('.cti-sidebar-tooltip');
    if (!tooltip) return;
    const row = tooltip.__ctiRow;
    if (row) {
      const previous = tooltip.__ctiPreviousDescription;
      if (previous) row.setAttribute('aria-describedby', previous); else row.removeAttribute('aria-describedby');
    }
    tooltip.remove();
  }
  function showSidebarTooltip(row, text, render) {
    hideSidebarTooltip();
    const tooltip = document.createElement('div');
    tooltip.className = 'cti-sidebar-tooltip';
    tooltip.id = 'cti-sidebar-tooltip';
    tooltip.setAttribute('role', 'tooltip');
    tooltip.lang = render.language();
    tooltip.__ctiRow = row;
    tooltip.__ctiPreviousDescription = row.getAttribute('aria-describedby') || '';
    row.setAttribute('aria-describedby', [tooltip.__ctiPreviousDescription, tooltip.id].filter(Boolean).join(' '));
    const content = document.createElement('div');
    content.textContent = text;
    const credit = document.createElement('span');
    credit.className = 'cti-sidebar-credit';
    credit.textContent = render.credit();
    tooltip.append(content, credit);
    document.body.appendChild(tooltip);
    const rect = row.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();
    const left = Math.min(window.innerWidth - tooltipRect.width - 12, Math.max(12, rect.right + 8));
    const top = Math.min(window.innerHeight - tooltipRect.height - 12, Math.max(12, rect.top + 30));
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
  }
  function installSidebarHoverDelegation(render) {
    const previous = window.__codexContextTokenInspectorSidebarDelegation;
    if (previous?.version === render.runtimeVersion) return;
    if (previous?.mouseover) document.removeEventListener('mouseover', previous.mouseover);
    if (previous?.mouseout) document.removeEventListener('mouseout', previous.mouseout);
    if (previous?.focusin) document.removeEventListener('focusin', previous.focusin);
    if (previous?.focusout) document.removeEventListener('focusout', previous.focusout);
    const mouseover = event => {
      const row = event.target?.closest?.(`[${sidebarHoverAttr}]`);
      if (row) setTimeout(() => showSidebarTooltip(row, row.getAttribute(sidebarHoverAttr) || '', render), 0);
    };
    const mouseout = event => {
      const row = event.target?.closest?.(`[${sidebarHoverAttr}]`);
      if (!row || (event.relatedTarget && row.contains(event.relatedTarget))) return;
      setTimeout(hideSidebarTooltip, 0);
    };
    const focusin = event => {
      const row = event.target?.closest?.(`[${sidebarHoverAttr}]`);
      if (row) showSidebarTooltip(row, row.getAttribute(sidebarHoverAttr) || '', render);
    };
    const focusout = event => {
      const row = event.target?.closest?.(`[${sidebarHoverAttr}]`);
      if (!row || (event.relatedTarget && row.contains(event.relatedTarget))) return;
      hideSidebarTooltip();
    };
    document.addEventListener('mouseover', mouseover);
    document.addEventListener('mouseout', mouseout);
    document.addEventListener('focusin', focusin);
    document.addEventListener('focusout', focusout);
    window.__codexContextTokenInspectorSidebarDelegation = {
      version: render.runtimeVersion,
      mouseover,
      mouseout,
      focusin,
      focusout,
    };
  }
  function assistantNodes() {
    const selectors = [
      '[data-content-search-assistant-turn-key]',
      '[data-local-conversation-final-assistant]',
      '[data-chatgpt-conversation-turn="true"]',
    ];
    const seen = new Set();
    const nodes = [];
    for (const selector of selectors) {
      document.querySelectorAll(selector).forEach(node => {
        const element = node.closest('[data-content-search-assistant-turn-key]') ||
          node.closest('[data-chatgpt-conversation-turn="true"]') ||
          node;
        if (!seen.has(element)) {
          seen.add(element);
          nodes.push(element);
        }
      });
      if (nodes.length) break;
    }
    return nodes.filter(node => !node.closest(`#${rootId}`));
  }
  function actionRowForAssistant(node) {
    const turn = node.closest('[data-turn-key], [data-chatgpt-conversation-turn="true"]') || node;
    const sentTime = turn.querySelector('[data-assistant-message-sent-time]');
    if (sentTime?.parentElement) return sentTime.parentElement;
    const candidates = Array.from(turn.querySelectorAll('span, div')).filter(element => {
      if (element.closest(`#${rootId}`) || element.hasAttribute(chipAttr)) return false;
      const text = (element.textContent || '').trim();
      return /^Work(?:ing|ed) for /.test(text) || /\b\d{1,2}:\d{2}\s?(?:AM|PM)\b/.test(text);
    });
    const candidate = candidates.find(element => /^Work(?:ing|ed) for /.test((element.textContent || '').trim())) ||
      candidates.find(element => /\b\d{1,2}:\d{2}\s?(?:AM|PM)\b/.test((element.textContent || '').trim())) ||
      null;
    return candidate?.parentElement || null;
  }
  function assistantChipTargets() {
    const targetsByHost = new Map();
    assistantNodes().forEach(node => {
      const actionRow = actionRowForAssistant(node);
      const host = actionRow?.parentElement || node;
      if (host) targetsByHost.set(host, {node, actionRow, host});
    });
    return Array.from(targetsByHost.values());
  }
  function directReplyChips(host) {
    return Array.from(host?.children || []).filter(child => child.hasAttribute(chipAttr));
  }
  function applyFooters(detail, render) {
    if (!detail) return;
    const targets = assistantChipTargets();
    const items = detail.assistantItems || [];
    const used = new Set();
    const keptChips = new Set();
    targets.forEach(({node, actionRow, host}, index) => {
      const item = visibleItemForNode(node, index, items, used, targets.length);
      if (!item?.footer) return;
      node.querySelector(`[${footerAttr}]`)?.remove();
      const sessionRound = item.roundIndex || index + 1;
      const sessionTotalRounds = item.totalRounds || items.length || targets.length;
      let chip = actionRow?.nextElementSibling?.hasAttribute(chipAttr)
        ? actionRow.nextElementSibling
        : directReplyChips(host)[0] || node.querySelector(`[${chipAttr}]`);
      if (!chip) {
        chip = document.createElement('div');
        chip.className = 'cti-reply-chip';
        chip.setAttribute(chipAttr, 'true');
      }
      keptChips.add(chip);
      chip.lang = render.language();
      if (actionRow?.parentElement === host) {
        if (chip.parentElement !== host || chip.previousElementSibling !== actionRow) {
          actionRow.insertAdjacentElement('afterend', chip);
        }
      } else if (chip.parentElement !== host) {
        host.appendChild(chip);
      }
      const chipText = render.chipText(item, sessionRound, sessionTotalRounds);
      if (chip.textContent !== chipText) chip.textContent = chipText;
      const title = render.title(item, sessionRound, sessionTotalRounds);
      if (chip.getAttribute('title') !== title) chip.setAttribute('title', title);
    });
    document.querySelectorAll(`[${chipAttr}]`).forEach(chip => {
      if (!keptChips.has(chip)) chip.remove();
    });
  }
  function clearFooters() {
    document.querySelectorAll(`[${footerAttr}], [${chipAttr}]`).forEach(node => node.remove());
  }
  function normalizedText(value) {
    return String(value || '')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .replace(/[`*~]/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  }
  function visibleItemForNode(node, index, items, used, visibleCount) {
    const nodeText = normalizedText(node.textContent);
    for (let itemIndex = 0; itemIndex < items.length; itemIndex += 1) {
      if (used.has(itemIndex)) continue;
      const prefix = normalizedText(items[itemIndex].textPrefix);
      if (prefix && nodeText.includes(prefix)) {
        used.add(itemIndex);
        return items[itemIndex];
      }
    }
    const fallbackStart = Math.max(0, items.length - visibleCount);
    const fallbackIndex = fallbackStart + index;
    if (items[fallbackIndex] && !used.has(fallbackIndex)) {
      used.add(fallbackIndex);
      return items[fallbackIndex];
    }
    return null;
  }
  function detailCandidates(payload) {
    if (payload.__ctiDetailCandidates) return payload.__ctiDetailCandidates;
    const details = new Map();
    if (payload.detail?.thread_id) details.set(String(payload.detail.thread_id), payload.detail);
    Object.values(payload.detailsByThread || {}).forEach(detail => {
      if (detail?.thread_id) details.set(String(detail.thread_id), detail);
    });
    payload.__ctiDetailCandidates = Array.from(details.values());
    return payload.__ctiDetailCandidates;
  }
  function detailPrefixes(detail) {
    if (detail.__ctiPrefixes) return detail.__ctiPrefixes;
    const items = detail?.assistantItems || [];
    detail.__ctiPrefixes = items
      .map((item, index) => ({index, prefix: normalizedText(item.textPrefix)}))
      .filter(item => item.prefix.length >= 24);
    return detail.__ctiPrefixes;
  }
  function textChunks(value) {
    return normalizedText(value)
      .split(/[，。！？；：、,.!?;:\n\r()[\]{}<>《》"'“”‘’|]+/)
      .map(chunk => chunk.trim())
      .filter(chunk => chunk.length >= 6);
  }
  function textMatchScore(nodeText, prefix) {
    if (nodeText.includes(prefix)) return 100 + Math.min(prefix.length, 120);
    const nodeHead = nodeText.slice(0, Math.min(120, nodeText.length));
    if (prefix.includes(nodeHead)) return 80 + Math.min(nodeHead.length, 120);
    const prefixHead = prefix.slice(0, Math.min(80, prefix.length));
    if (nodeText.includes(prefixHead)) return 60 + Math.min(prefixHead.length, 80);
    let chunkScore = 0;
    let chunkMatches = 0;
    for (const chunk of textChunks(prefix)) {
      if (nodeText.includes(chunk)) {
        chunkMatches += 1;
        chunkScore += Math.min(chunk.length, 40);
      }
    }
    if (chunkMatches >= 2 || chunkScore >= 18) return chunkScore;
    chunkScore = 0;
    chunkMatches = 0;
    for (const chunk of textChunks(nodeText)) {
      if (prefix.includes(chunk)) {
        chunkMatches += 1;
        chunkScore += Math.min(chunk.length, 40);
      }
    }
    return chunkMatches >= 2 || chunkScore >= 18 ? chunkScore : 0;
  }
  function scoreDetailForNodes(detail, nodes) {
    if (!nodes.length) return 0;
    const prefixes = detailPrefixes(detail);
    if (!prefixes.length) return 0;
    let score = 0;
    const used = new Set();
    for (const node of nodes) {
      const nodeText = normalizedText(node.textContent);
      if (nodeText.length < 24) continue;
      for (const item of prefixes) {
        if (used.has(item.index)) continue;
        const matchScore = textMatchScore(nodeText, item.prefix);
        if (matchScore > 0) {
          used.add(item.index);
          score += matchScore;
          break;
        }
      }
    }
    return score;
  }
  function detailForVisiblePage(payload) {
    const nodes = assistantNodes();
    if (!nodes.length) return null;
    const signature = nodes.map(node => normalizedText(node.textContent).slice(0, 180)).join('||');
    const cached = payload.__ctiVisibleMatchCache;
    if (cached?.signature === signature && cached.threadId) {
      const detail = detailCandidates(payload).find(item => String(item.thread_id) === String(cached.threadId));
      if (detail) return detail;
    }
    let best = null;
    let bestScore = 0;
    for (const detail of detailCandidates(payload)) {
      const score = scoreDetailForNodes(detail, nodes);
      if (score > bestScore) {
        best = detail;
        bestScore = score;
      }
    }
    payload.__ctiVisibleMatchCache = {signature, threadId: bestScore > 0 ? best?.thread_id : null, score: bestScore};
    return bestScore > 0 ? best : null;
  }
  return {
    activeThreadId,
    summaryForActiveThread,
    detailForActiveThread,
    projectSidebar,
    clearSidebar,
    hideSidebarTooltip,
    installSidebarHoverDelegation,
    assistantNodes,
    applyFooters,
    clearFooters,
    detailForVisiblePage,
  };
}

function createPageRefreshController({page, renderHud, applyFooters, clearFooters, summaryHover, isApplying}) {
  let observer = null;
  let timer = null;
  let freshnessTimer = null;
  let payload = null;
  function scheduleDetailApply() {
    if (window.__codexContextTokenInspectorDetailTimer) {
      clearTimeout(window.__codexContextTokenInspectorDetailTimer);
    }
    if (window.__codexContextTokenInspectorIdleCallback && window.cancelIdleCallback) {
      window.cancelIdleCallback(window.__codexContextTokenInspectorIdleCallback);
      window.__codexContextTokenInspectorIdleCallback = null;
    }
    const run = () => {
      window.__codexContextTokenInspectorDetailTimer = null;
      const work = () => {
        if (!payload || isApplying()) return;
        window.__codexContextTokenInspectorApplying = true;
        try {
          const detail = page.detailForActiveThread(payload) || page.detailForVisiblePage(payload);
          payload.currentDetailThreadId = detail?.thread_id || null;
          renderHud(payload, detail);
          if (detail) applyFooters(detail);
          else clearFooters();
        } finally {
          setTimeout(() => { window.__codexContextTokenInspectorApplying = false; }, 0);
        }
      };
      if (window.requestIdleCallback) {
        window.__codexContextTokenInspectorIdleCallback = window.requestIdleCallback(work, {timeout: 900});
      } else {
        setTimeout(work, 0);
      }
    };
    window.__codexContextTokenInspectorDetailTimer = setTimeout(run, 220);
  }
  function apply() {
    if (!payload) return;
    window.__codexContextTokenInspectorApplying = true;
    try {
      payload.activeThreadId = page.activeThreadId() || payload.activeThreadId;
      page.projectSidebar(payload.summaries || [], summaryHover);
      const detail = page.detailForActiveThread(payload) || page.detailForVisiblePage(payload);
      payload.currentDetailThreadId = detail?.thread_id || null;
      renderHud(payload, detail);
    } finally {
      setTimeout(() => { window.__codexContextTokenInspectorApplying = false; }, 0);
    }
    scheduleDetailApply();
  }
  const controller = {
    update(nextPayload) {
      payload = nextPayload;
      window.__codexContextTokenInspectorPayload = payload;
      if (freshnessTimer) clearTimeout(freshnessTimer);
      const remaining = typeof payload?.observedAt === 'number'
        ? Math.max(0, 120000 - (Date.now() - payload.observedAt * 1000))
        : 120000;
      freshnessTimer = setTimeout(apply, remaining + 100);
      window.__ctiFreshnessTimer = freshnessTimer;
      if (observer) return;
      observer = new MutationObserver(records => {
        if (isApplying()) return;
        const activeChanged = records.some(record => record.type === 'attributes' &&
          (record.attributeName === 'data-app-action-sidebar-thread-active' || record.attributeName === 'aria-current'));
        if (timer && !activeChanged) return;
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => {
          timer = null;
          apply();
        }, activeChanged ? 80 : 300);
      });
      observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['data-app-action-sidebar-thread-active', 'aria-current'],
      });
      window.__codexContextTokenInspectorObserver = observer;
    },
    apply,
    dispose() {
      observer?.disconnect();
      if (timer) clearTimeout(timer);
      if (freshnessTimer) clearTimeout(freshnessTimer);
      if (window.__codexContextTokenInspectorObserver === observer) {
        window.__codexContextTokenInspectorObserver = null;
      }
      if (window.__ctiFreshnessTimer === freshnessTimer) window.__ctiFreshnessTimer = null;
      observer = null;
      timer = null;
      freshnessTimer = null;
      payload = null;
    },
  };
  return controller;
}
"""


def read(client: Any) -> dict[str, Any]:
    value = client.evaluate(PROBE)
    return value if isinstance(value, dict) else {}
