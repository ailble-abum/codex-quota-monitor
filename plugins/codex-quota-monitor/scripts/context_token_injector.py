#!/usr/bin/env python3
"""Inject Codex context/token stats into the existing Codex Desktop window.

This helper talks to a Codex Desktop renderer through Chrome DevTools Protocol.
It does not modify Codex.app, app.asar, app state, or local session JSONL files.
Codex must be launched with a local --remote-debugging-port first.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import context_token_inspector as inspector
from cdp_transport import CDPClient, CDPError, devtools_targets, select_target
from injector_status import write_status
from payload_builder import (DETAIL_SESSION_LIMIT, build_payload, normalize_thread_id,
                             session_file_for_thread, thread_keys)
from platform_paths import runtime_root
from quota_reader import QuotaReader
from quota_alerts import QuotaAlerts
import context_health
from companion_art import COMPANION_ART
from update_check import UpdateChecker
from usage_history import History, recent_breakdown

QUOTA_READER = QuotaReader()
QUOTA_ALERTS = QuotaAlerts()
UPDATE_CHECKER = UpdateChecker()
HISTORY = History()


DEFAULT_PORT = 9222


def runtime_state(client: CDPClient) -> dict[str, Any]:
    expression = r"""
(() => {
  function attr(el, name) { return el && el.getAttribute ? el.getAttribute(name) : null; }
  function activeSidebarRow() {
    return document.querySelector('[data-app-action-sidebar-thread-row][data-app-action-sidebar-thread-active="true"]') ||
      document.querySelector('[data-app-action-sidebar-thread-row][aria-current="page"]') ||
      document.querySelector('[data-app-action-sidebar-thread-active="true"]') ||
      document.querySelector('[data-app-action-sidebar-thread-row][data-app-action-sidebar-thread-active]:not([data-app-action-sidebar-thread-active="false"])');
  }
  const activeRow =
    activeSidebarRow();
  const activeId =
    attr(activeRow, 'data-app-action-sidebar-thread-id') ||
    attr(activeRow && activeRow.querySelector('[data-app-action-sidebar-thread-id]'), 'data-app-action-sidebar-thread-id') ||
    attr(document.querySelector('[data-conversation-id]'), 'data-conversation-id') ||
    attr(document.querySelector('[data-above-composer-conversation-id]'), 'data-above-composer-conversation-id') ||
    null;
  const refresh = window.__ctiRefreshRequested === true;
  window.__ctiRefreshRequested = false;
  // Which selectors landed is what separates "Codex updated its DOM" from
  // "the overlay stopped updating". A thread list with no marked-active row,
  // or a page with no thread rows at all, is drift and is reported rather
  // than silently drawing a smaller panel.
  const dom = {
    sidebarRows: document.querySelectorAll('[data-app-action-sidebar-thread-row]').length,
    activeRow: !!activeRow,
    conversationId: !!activeId
  };
  return { href: location.href, title: document.title, activeThreadId: activeId,
    dom, refresh, alerts: localStorage.getItem('cti-alerts') === 'true',
    language: String(document.documentElement.lang || navigator.language || 'en').startsWith('zh') ? 'zh' : 'en' };
})()
"""
    value = client.evaluate(expression)
    return value if isinstance(value, dict) else {}


INJECTION_SCRIPT = r"""
(payload => {
  // Bump this when a long-lived renderer has to re-derive something from the
  // new script: stacked observers and timers are torn down, and the companion
  // bitmap is rebuilt from the new data URIs. A renderer may still contain an
  // observer from an older plugin release.
  const RUNTIME_VERSION = 29;
  const ROOT_ID = 'codex-context-token-inspector-root';
  const STYLE_ID = 'codex-context-token-inspector-style';
  const FOOTER_ATTR = 'data-context-token-footer';
  const CHIP_ATTR = 'data-context-token-chip';
  const BADGE_ATTR = 'data-context-token-badge';
  const SIDEBAR_HOVER_ATTR = 'data-context-token-sidebar-hover';
  const COLLAPSE_KEY = 'codex-context-token-inspector-collapsed';
  const POSITION_KEY = 'codex-context-token-inspector-position';
  const UNIT_KEY = 'codex-context-token-inspector-unit';
  const LAYOUT_PRESET_KEY = 'cti-layout-preset';
  const UNIT_DEFAULTED_KEY = 'codex-context-token-inspector-unit-defaulted';
  const EDGE_DOCK_KEY = 'cti-edge-dock';
  const SKIN_KEY = 'cti-mascot-skin';
  const SKINS_OPEN_KEY = 'cti-skins-open';
  const MASCOT_ID = 'codex-context-token-inspector-mascot';
  const previousRuntimeVersion = window.__codexContextTokenInspectorRuntimeVersion;
  const runtimeChanged = previousRuntimeVersion !== RUNTIME_VERSION;
  window.__codexContextTokenInspectorRuntimeVersion = RUNTIME_VERSION;

  const I18N = {
    en: {
      monitor: 'Usage', tokenUnit: 'Token unit', rawUnit: 'raw',
      expandMonitor: 'Expand Monitor', collapseMonitor: 'Collapse Monitor',
      status: 'status', left: 'left', context: 'context', turn: 'Latest request', session: 'session',
      inputShort: 'in', cachedShort: 'cached', outputShort: 'out', reasoningShort: 'reason',
      sessionTotal: 'Session total', input: 'Input', cachedInput: 'Cached input',
      output: 'Output', reasoning: 'Reasoning', token: 'Token', current: 'Current',
      total: 'Total', rounds: 'Rounds', user: 'User', assistant: 'Assistant',
      contextTitle: 'Context', turnTitle: 'Turn', sessionTitle: 'Session', tokens: 'tokens',
      userRounds: 'User rounds', assistantRounds: 'Assistant rounds',
      noRecords: 'No token records found.', madeBy: 'Made by Ailble',
      unknown: 'UNKNOWN', high: 'HIGH', watch: 'WATCH', ok: 'OK',
    },
    zh: {
      monitor: '用量', tokenUnit: 'Token 单位', rawUnit: '原值',
      expandMonitor: '展开监控', collapseMonitor: '收起监控',
      status: '状态', left: '剩余', context: '上下文', turn: '最近请求', session: '会话',
      inputShort: '输入', cachedShort: '缓存', outputShort: '输出', reasoningShort: '推理',
      sessionTotal: '会话总计', input: '输入', cachedInput: '缓存输入',
      output: '输出', reasoning: '推理', token: 'Token', current: '当前',
      total: '总计', rounds: '轮次', user: '用户', assistant: '助手',
      contextTitle: '上下文', turnTitle: '本轮', sessionTitle: '会话', tokens: 'Token',
      userRounds: '用户轮次', assistantRounds: '助手轮次',
      noRecords: '暂无 Token 记录。', madeBy: 'Ailble 制作',
      unknown: '未知', high: '高', watch: '注意', ok: '正常',
    },
  };

  function uiLanguage() {
    const preferred=localStorage.getItem('cti-language');
    if(['zh','en'].includes(preferred))return preferred;
    const language = String(document.documentElement.lang || navigator.language || 'en').toLowerCase();
    return language.startsWith('zh') ? 'zh' : 'en';
  }
  function tr(key) {
    const language = uiLanguage();
    return I18N[language][key] || I18N.en[key] || key;
  }
  function labeled(key, value) {
    return uiLanguage() === 'zh' ? `${tr(key)}：${value}` : `${tr(key)}: ${value}`;
  }
  function parenthesized(value) {
    return uiLanguage() === 'zh' ? `（${value}）` : `(${value})`;
  }
  function joined(values) {
    return values.join(uiLanguage() === 'zh' ? '，' : ', ');
  }

  // Bitmap companions, generated by scripts/build_companion_art.py. Each render
  // is cropped flush against the character's cut edge, so the overlay can pin
  // the image straight to the edge it docks to. A skin with no artwork here
  // falls back to its vector mascot below.
  const MASCOT_ART = __COMPANION_ART__;
  const MASCOT_SKINS = {
    cat: {zh:'薄荷黑猫', en:'Mint Cat', accent:'#62efc2', ring:[11.5,23,42]},
    candy: {zh:'软糖女孩', en:'Candy Girl', accent:'#ff9fc5', ring:[15,18,28]},
    corgi: {zh:'柯基助手', en:'Corgi Helper', accent:'#f2ae62', ring:[18,20,34]},
    mint: {zh:'薄荷萌男', en:'Mint Boy', accent:'#70d4a6', ring:[14.5,16,27]},
    frost: {zh:'霜夜先生', en:'Mr. Frost', accent:'#8ab5ff', ring:[15,17,27]},
    tea: {zh:'红茶御姐', en:'Tea Lady', accent:'#c97b88', ring:[17,18,30]},
  };
  function mascotSvg(id) {
    const art={
      cat:`<svg viewBox="0 0 44 48" aria-hidden="true"><path d="M7 18 9 5l9 7c3-1 7-1 10 0l8-7 2 14" fill="#202329" stroke="#30353d" stroke-width="1.5" stroke-linejoin="round"/><path d="M5 25C5 14 12 9 22 9s17 5 17 16c0 10-6 17-17 17S5 35 5 25z" fill="#202329"/><path d="m10 10 1-3 4 4M34 10l-1-3-4 4" fill="#62efc2" opacity=".85"/><rect x="13" y="21" width="4" height="9" rx="2" fill="#62efc2"/><rect x="27" y="21" width="4" height="9" rx="2" fill="#62efc2"/><path d="M20 32q2 2 4 0M9 33l7 1M35 33l-7 1" fill="none" stroke="#62efc2" stroke-width="1.2" stroke-linecap="round" opacity=".8"/><circle cx="37" cy="35" r="7" fill="#292d34" stroke="#363b44" stroke-width="1.5"/></svg>`,
      candy:`<svg viewBox="0 0 44 48" aria-hidden="true"><circle cx="11" cy="10" r="7" fill="#6b3d35"/><circle cx="33" cy="10" r="7" fill="#6b3d35"/><path d="M5 27c0-13 7-20 17-20s17 7 17 20v15H5z" fill="#714239"/><circle cx="22" cy="25" r="13" fill="#ffd8c2"/><path d="M10 20c2-9 8-13 14-12 6 1 10 5 11 12-5-1-8-4-10-8-2 5-7 8-15 8z" fill="#714239"/><circle cx="17" cy="25" r="1.5" fill="#3e2b2a"/><circle cx="27" cy="25" r="1.5" fill="#3e2b2a"/><path d="M19 31q3 3 6 0" fill="none" stroke="#c76870" stroke-width="1.4" stroke-linecap="round"/><path d="M8 48v-8c2-6 7-9 14-9s12 3 14 9v8" fill="#ff9fc5"/><path d="m34 8 1.3 2.7 3 .4-2.2 2.1.5 3-2.6-1.4-2.7 1.4.6-3-2.2-2.1 3-.4z" fill="#ffe07d"/><circle cx="9" cy="43" r="4" fill="#ffd8c2"/><circle cx="35" cy="43" r="4" fill="#ffd8c2"/></svg>`,
      corgi:`<svg viewBox="0 0 44 48" aria-hidden="true"><path d="m5 19 2-15 11 9M39 19 37 4 26 13" fill="#d9863b" stroke="#a95e27" stroke-width="1.5"/><path d="m8 8 3 8 5-3M36 8l-3 8-5-3" fill="#ffb98a"/><path d="M5 27c0-12 7-19 17-19s17 7 17 19v15H5z" fill="#dc8a42"/><path d="M18 9h8l3 17-7 8-7-8z" fill="#fff0dc"/><ellipse cx="22" cy="29" rx="10" ry="8" fill="#fff0dc"/><circle cx="15" cy="24" r="2" fill="#33241e"/><circle cx="29" cy="24" r="2" fill="#33241e"/><path d="m19 28 3-2 3 2-3 3z" fill="#33241e"/><path d="M18 33q4 4 8 0" fill="#ef7b82"/><path d="M7 48v-8c2-5 7-8 15-8s13 3 15 8v8" fill="#c97835"/><circle cx="9" cy="43" r="4" fill="#fff0dc"/><circle cx="35" cy="43" r="4" fill="#fff0dc"/></svg>`,
      mint:`<svg viewBox="0 0 44 48" aria-hidden="true"><path d="M6 26C6 12 12 5 23 5c10 0 16 8 15 21v16H6z" fill="#2c292d"/><circle cx="22" cy="25" r="13" fill="#f3c8ad"/><path d="M8 19C10 7 18 4 25 6c7 1 11 7 11 14-5-1-9-5-10-9-3 5-8 8-18 8z" fill="#302d31"/><path d="M11 14c4-6 12-8 18-6M18 7c-3 3-5 7-5 11" fill="none" stroke="#49444b" stroke-width="3" stroke-linecap="round"/><circle cx="17" cy="25" r="1.5" fill="#352c2c"/><circle cx="27" cy="25" r="1.5" fill="#352c2c"/><path d="M19 31q3 2 6 0" fill="none" stroke="#9b5f62" stroke-width="1.4" stroke-linecap="round"/><path d="M7 48v-8c2-6 7-9 15-9s13 3 15 9v8" fill="#70d4a6"/><path d="m18 35 4 4 4-4" fill="none" stroke="#d9fff0" stroke-width="1.5"/><circle cx="9" cy="43" r="4" fill="#f3c8ad"/><circle cx="35" cy="43" r="4" fill="#f3c8ad"/></svg>`,
      frost:`<svg viewBox="0 0 44 48" aria-hidden="true"><path d="M5 27C5 12 12 5 23 5s16 8 16 22v15H5z" fill="#171a20"/><circle cx="22" cy="25" r="13" fill="#efd1c1"/><path d="M7 19C9 9 16 4 24 5c8 0 13 6 13 15-6-2-9-6-10-10-4 5-9 8-20 9z" fill="#d9e1ea"/><path d="M13 8c8-4 15-1 18 2-6 1-10 4-15 9" fill="none" stroke="#788493" stroke-width="3" stroke-linecap="round"/><path d="M15 25h4M25 25h4" stroke="#578ec7" stroke-width="1.7" stroke-linecap="round"/><path d="M20 31q2 1 4 0" fill="none" stroke="#915d62" stroke-width="1.2" stroke-linecap="round"/><path d="M6 48v-9c3-6 8-8 16-8s13 2 16 8v9" fill="#20252d"/><path d="m15 34 7 8 7-8" fill="#0e1116"/><path d="m20 38 2 3 2-3" fill="#8ab5ff"/><circle cx="9" cy="43" r="4" fill="#252b34"/><circle cx="35" cy="43" r="4" fill="#252b34"/></svg>`,
      tea:`<svg viewBox="0 0 44 48" aria-hidden="true"><path d="M4 28C4 12 12 4 22 4s18 8 18 24v17H4z" fill="#5d2630"/><circle cx="22" cy="24" r="13" fill="#f2c5ad"/><path d="M7 20C9 8 16 4 24 5c8 1 13 7 13 15-5-2-9-6-10-10-4 5-10 8-20 10z" fill="#6b2d37"/><path d="M8 16c-2 9-1 19 4 28M36 16c2 9 1 19-4 28" fill="none" stroke="#7e3541" stroke-width="4" stroke-linecap="round"/><path d="M15 24q2-2 4 0M25 24q2-2 4 0" fill="none" stroke="#4a2929" stroke-width="1.5" stroke-linecap="round"/><path d="M19 30q3 3 6 0" fill="none" stroke="#b74f61" stroke-width="1.4" stroke-linecap="round"/><path d="M7 48v-9c3-6 8-8 15-8s12 2 15 8v9" fill="#8e3446"/><path d="m18 33 4 7 4-7" fill="#f7e6d3"/><circle cx="34" cy="25" r="2" fill="none" stroke="#e7bd62" stroke-width="1.2"/><circle cx="9" cy="43" r="4" fill="#f2c5ad"/><circle cx="35" cy="43" r="4" fill="#f2c5ad"/></svg>`,
    };
    return art[id] || art.cat;
  }
  function mascotSkin() {
    const value=localStorage.getItem(SKIN_KEY);
    return MASCOT_SKINS[value] ? value : 'cat';
  }
  function edgeDockEnabled() { return localStorage.getItem(EDGE_DOCK_KEY)!=='false'; }
  function mascotArt(id) { return MASCOT_ART[id] || ''; }
  function mascotMarkup(id, className) {
    const art=mascotArt(id);
    return art ? `<img class="${className}" src="${art}" alt="" draggable="false">` : mascotSvg(id);
  }
  function skinButtons() {
    const zh=uiLanguage()==='zh';
    return Object.entries(MASCOT_SKINS).map(([id,skin])=>`<button type="button" class="cti-skin-button" data-skin-choice="${id}" aria-label="${zh?skin.zh:skin.en}" title="${zh?skin.zh:skin.en}">${mascotMarkup(id,'cti-skin-art')}<small>${zh?skin.zh:skin.en}</small></button>`).join('');
  }
  function updateSkinButtons(root) {
    const zh=uiLanguage()==='zh';
    root.querySelectorAll('[data-skin-choice]').forEach(button=>{
      const active=button.dataset.skinChoice===mascotSkin();
      button.dataset.active=String(active);button.setAttribute('aria-pressed',String(active));
    });
    // The picker ships collapsed, so its summary carries the only hint of
    // which companion is currently docked.
    const label=root.querySelector('[data-skin-current]');
    if(label){const skin=MASCOT_SKINS[mascotSkin()];label.textContent=skin?(zh?skin.zh:skin.en):'';}
  }

  function n(value) {
    return value == null ? '-' : new Intl.NumberFormat().format(value);
  }
  function ensureDefaultUnit() {
    if (!localStorage.getItem(UNIT_DEFAULTED_KEY)) {
      localStorage.setItem(UNIT_KEY, 'auto');
      localStorage.setItem(UNIT_DEFAULTED_KEY, 'true');
    }
  }
  function unitMode() {
    const value = localStorage.getItem(UNIT_KEY);
    return ['auto', 'raw', 'k', 'm'].includes(value) ? value : 'auto';
  }
  function token(value) {
    if (value == null || Number.isNaN(Number(value))) return '-';
    const number = Number(value);
    const mode = unitMode();
    if (mode === 'auto') {
      const scale = Math.abs(number) >= 1000000 ? 1000000 : Math.abs(number) >= 1000 ? 1000 : 1;
      return new Intl.NumberFormat(undefined, {maximumFractionDigits: scale === 1 ? 0 : 1}).format(number/scale) + (scale === 1000000 ? 'M' : scale === 1000 ? 'K' : '');
    }
    if (mode === 'k') {
      const scaled = number / 1000;
      const digits = Math.abs(scaled) >= 1000 ? 0 : Math.abs(scaled) >= 100 ? 1 : 2;
      return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(scaled)}K`;
    }
    if (mode === 'm') return `${(number / 1000000).toFixed(Math.abs(number) >= 10000000 ? 1 : 2)}M`;
    return n(number);
  }
  function pct(value) {
    return typeof value === 'number' ? `${value.toFixed(1)}%` : '-';
  }
  function quotaTone(remaining) {
    return typeof remaining !== 'number' || !Number.isFinite(remaining) ? 'unknown' : remaining <= 20 ? 'low' : remaining <= 50 ? 'watch' : 'safe';
  }
  function contextTone(used) {
    return typeof used !== 'number' || !Number.isFinite(used) ? 'unknown' : used >= 85 ? 'low' : used >= 70 ? 'watch' : 'safe';
  }
  function toneLabel(tone) {
    const zh = uiLanguage() === 'zh';
    return ({safe:zh?'余量充足':'Comfortable',watch:zh?'留意用量':'Watch usage',low:zh?'额度偏低':'Running low',unknown:zh?'尚未更新':'Unavailable'})[tone];
  }
  // The collapsed bar is the glanceable view, so it answers the question the
  // panel exists for - whether the account can carry the work ahead - rather
  // than repeating the percentage the meter beside it already draws.
  function shortDuration(seconds) {
    if (!(seconds > 0)) return '0m';
    if (seconds < 60) return '<1m';
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return `${minutes}m`;
    const hours = seconds / 3600;
    return hours < 24 ? `${hours < 10 ? hours.toFixed(1) : Math.round(hours)}h` : `${Math.round(hours / 24)}d`;
  }
  function durationPhrase(seconds) {
    const zh = uiLanguage() === 'zh';
    if (!(seconds > 0)) return zh ? '不足 1 分钟' : 'under a minute';
    const minutes = seconds / 60;
    if (minutes < 60) return zh ? `${Math.round(minutes)} 分钟` : `${Math.round(minutes)} min`;
    const hours = minutes / 60;
    return hours < 48 ? (zh ? `${hours.toFixed(1)} 小时` : `${hours.toFixed(1)} hours`)
                      : (zh ? `${(hours / 24).toFixed(1)} 天` : `${(hours / 24).toFixed(1)} days`);
  }
  // A window that refills before it would run out cannot bind, so its honest
  // figure is a floor rather than a measurement. The "≥" is what keeps a
  // comfortable account from being shown a number that reads as a deadline.
  function windowBudgetText(item) {
    const resetIn = typeof item?.resetsAt === 'number' ? item.resetsAt - Date.now() / 1000 : null;
    const exhaust = typeof item?.exhaustInSec === 'number' ? item.exhaustInSec : null;
    if (exhaust != null && resetIn != null && resetIn > 0) {
      return exhaust < resetIn ? shortDuration(exhaust) : `≥${shortDuration(resetIn)}`;
    }
    if (resetIn != null && resetIn > 0) return `≥${shortDuration(resetIn)}`;
    return exhaust != null ? shortDuration(exhaust) : null;
  }
  function accountBudgetText(quota) {
    const budget = quota?.budget;
    if (!budget || typeof budget.seconds !== 'number') return '';
    const zh = uiLanguage() === 'zh', floor = budget.kind === 'floor';
    return `${floor ? (zh ? '至少还能用 ' : 'at least ') : (zh ? '按当前速度还能用 ' : 'at this pace about ')}${durationPhrase(budget.seconds)}`;
  }
  function nearestResetText(windows) {
    const stamps = (windows || []).map(item => item?.resetsAt).filter(value => typeof value === 'number');
    if (!stamps.length) return '';
    return new Date(Math.min(...stamps) * 1000)
      .toLocaleString(uiLanguage() === 'zh' ? 'zh-CN' : 'en', {month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'});
  }
  function windowLabel(item, compact=false) {
    const minutes=item.duration,zh=uiLanguage()==='zh';
    let label=minutes===300?'5h':minutes===10080?'7d':typeof minutes==='number' && minutes>0?(minutes%1440===0?`${minutes/1440}d`:minutes%60===0?`${minutes/60}h`:`${minutes}m`):(item.key==='primary'?(zh?'主窗口':'Primary'):(zh?'次窗口':'Secondary'));
    return label+(zh?' 剩余':compact?' left':' remaining');
  }
  function pressure(value) {
    if (typeof value !== 'number') return tr('unknown');
    if (value >= 85) return tr('high');
    if (value >= 70) return tr('watch');
    return tr('ok');
  }
  function remainingContext(item) {
    if (typeof item?.latest_context_tokens !== 'number' || typeof item?.context_window !== 'number') return null;
    return Math.max(item.context_window - item.latest_context_tokens, 0);
  }
  function summaryHover(item) {
    return [
      labeled('sessionTotal', token(item.session_total_tokens)),
      labeled('input', token(item.session_input_tokens)),
      labeled('cachedInput', token(item.session_cached_input_tokens)),
      labeled('output', token(item.session_output_tokens)),
      labeled('reasoning', token(item.session_reasoning_tokens)),
    ].join('\n');
  }
  function itemChip(item, roundIndex, totalRounds) {
    const usage = item?.tokenUsage || {};
    const userIndex = item.userTurnIndex;
    const userTotal = item.userTotalTurns;
    const assistantIndex = item.assistantTurnIndex || item.roundIndex || roundIndex;
    const assistantTotal = item.assistantTotalTurns || item.totalRounds || totalRounds;
    const roundValues = userIndex && userTotal
      ? `${tr('user')} ${userIndex}/${userTotal}  | ${tr('assistant')} ${assistantIndex}/${assistantTotal}`
      : `${tr('assistant')} ${assistantIndex}/${assistantTotal}`;
    const current = `${tr('current')} ${token(usage.latest_context_tokens)}/${token(usage.context_window)} ${parenthesized(pct(usage.latest_context_percent))}`;
    return `${labeled('token', current)} | ${tr('total')} ${token(usage.latest_turn_total_tokens)}/${token(usage.session_total_tokens)}   ` +
      labeled('rounds', roundValues);
  }
  function itemTitle(item, roundIndex, totalRounds) {
    const usage = item?.tokenUsage || {};
    const userIndex = item.userTurnIndex;
    const userTotal = item.userTotalTurns;
    const assistantIndex = item.assistantTurnIndex || item.roundIndex || roundIndex;
    const assistantTotal = item.assistantTotalTurns || item.totalRounds || totalRounds;
    const turnBreakdown = joined([
      `${tr('inputShort')} ${token(usage.latest_turn_input_tokens)}`,
      `${tr('outputShort')} ${token(usage.latest_turn_output_tokens)}`,
      `${tr('reasoningShort')} ${token(usage.latest_turn_reasoning_tokens)}`,
    ]);
    const lines = [
      labeled('contextTitle', `${token(usage.latest_context_tokens)} / ${token(usage.context_window)} ${parenthesized(pct(usage.latest_context_percent))}`),
      labeled('turnTitle', `${token(usage.latest_turn_total_tokens)} ${tr('tokens')} ${parenthesized(turnBreakdown)}`),
      labeled('sessionTitle', `${token(usage.session_total_tokens)} ${tr('tokens')}`),
    ];
    if (userIndex && userTotal) lines.push(labeled('userRounds', `${userIndex}/${userTotal}`));
    lines.push(labeled('assistantRounds', `${assistantIndex}/${assistantTotal}`));
    return lines.join('\n');
  }
  function rowThreadId(row) {
    return row.getAttribute('data-app-action-sidebar-thread-id') ||
      row.querySelector('[data-app-action-sidebar-thread-id]')?.getAttribute('data-app-action-sidebar-thread-id') ||
      null;
  }
  function normalizeThreadId(threadId) {
    return String(threadId || '').replace(/^local:/, '');
  }
  function threadKeys(threadId) {
    const normalized = normalizeThreadId(threadId);
    return [String(threadId || ''), normalized, `local:${normalized}`].filter(Boolean);
  }
  function activeSidebarRow() {
    return document.querySelector('[data-app-action-sidebar-thread-row][data-app-action-sidebar-thread-active="true"]') ||
      document.querySelector('[data-app-action-sidebar-thread-row][aria-current="page"]') ||
      document.querySelector('[data-app-action-sidebar-thread-active="true"]') ||
      document.querySelector('[data-app-action-sidebar-thread-row][data-app-action-sidebar-thread-active]:not([data-app-action-sidebar-thread-active="false"])');
  }
  function activeThreadId() {
    const row = activeSidebarRow();
    return row ? rowThreadId(row) : null;
  }
  function ensureStyle() {
    let style = document.getElementById(STYLE_ID);
    if (!style) {
      style = document.createElement('style');
      style.id = STYLE_ID;
      document.head.appendChild(style);
    }
    const css = `
      [${BADGE_ATTR}] {
        display: inline-flex;
        align-items: center;
        width: fit-content;
        max-width: 100%;
        margin-top: 4px;
        padding: 2px 6px;
        border-radius: 6px;
        background: color-mix(in srgb, CanvasText 9%, transparent);
        color: color-mix(in srgb, CanvasText 72%, transparent);
        font: 11px/1.2 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        pointer-events: none;
      }
      .cti-hud {
        --cti-safe: light-dark(#18734e, #70d4a6);
        --cti-watch: light-dark(#285dc1, #8ab5ff);
        --cti-low: light-dark(#bb3443, #ff929c);
        --cti-tone: color-mix(in srgb, CanvasText 60%, transparent);
        box-sizing: border-box;
        position: fixed;
        left: 14px;
        bottom: 16px;
        z-index: 2147483647;
        width: 292px;
        min-width: 180px;
        max-width: min(760px, calc(100vw - 28px));
        border: 1px solid color-mix(in srgb, CanvasText 10%, transparent);
        border-radius: 18px;
        background: Canvas;
        color: CanvasText;
        box-shadow: 0 2px 5px #00000005, 0 12px 36px #00000012;
        backdrop-filter: blur(16px);
        font: 12px/1.35 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        user-select: none;
        transition: left .2s ease, top .2s ease, opacity .15s ease, box-shadow .15s ease;
      }
      .cti-hud[data-docked="true"][data-revealed="false"] { opacity:0; pointer-events:none; }
      .cti-hud[data-snap-edge] { box-shadow:0 0 0 2px color-mix(in srgb,var(--cti-safe) 55%,transparent),0 12px 36px #0002; }
      .cti-edge-mascot {
        --cti-mascot-accent:#70d4a6;
        /* The gauge speaks the panel's tier palette, but the companion is a
           body child and inherits none of .cti-hud's variables. */
        --cti-safe: light-dark(#18734e, #70d4a6);
        --cti-watch: light-dark(#285dc1, #8ab5ff);
        --cti-low: light-dark(#bb3443, #ff929c);
        position:fixed;
        z-index:2147483647;
        display:none;
        place-items:center;
        width:44px;
        height:48px;
        padding:0;
        cursor:ns-resize;
        touch-action:none;
        color:CanvasText;
        user-select:none;
        -webkit-app-region:no-drag !important;
        transition:transform .16s ease,box-shadow .16s ease,filter .16s ease;
      }
      .cti-edge-mascot[data-visible="true"] { display:grid; }
      .cti-edge-mascot svg { width:42px; height:46px; overflow:visible; filter:drop-shadow(0 2px 2px #0005); }
      /* A bitmap companion already has its own shading and silhouette, so it
         floats free: no plate, no border, nothing drawn around the character.
         The glass card survives only for the vector fallback, whose flat fills
         would lose their outline against a light canvas. */
      .cti-edge-mascot[data-art="true"] { width:auto; min-width:0; height:auto; padding:0; border:0; border-radius:0; background:none; box-shadow:none; }
      .cti-edge-mascot:not([data-art="true"]) {
        border:1px solid color-mix(in srgb,var(--cti-mascot-accent) 42%,transparent);
        border-radius:16px 0 0 16px;
        background:color-mix(in srgb,Canvas 91%,var(--cti-mascot-accent) 9%);
        box-shadow:0 8px 24px #0004,inset 0 0 16px color-mix(in srgb,var(--cti-mascot-accent) 10%,transparent);
      }
      .cti-edge-mascot[data-art="true"] img { display:block; height:48px; width:auto; }
      .cti-edge-mascot[data-art="true"] img { position:relative; z-index:1; }
      .cti-edge-mascot[data-art="true"][data-edge="left"] img { transform:scaleX(-1); }
      .cti-edge-mascot:hover,.cti-edge-mascot:focus-visible { transform:translateX(-3px) scale(1.04); outline:none; }
      .cti-edge-mascot:not([data-art="true"]):hover,.cti-edge-mascot:not([data-art="true"]):focus-visible { box-shadow:0 8px 26px #0005,0 0 0 2px color-mix(in srgb,var(--cti-mascot-accent) 45%,transparent); }
      .cti-edge-mascot[data-art="true"]:hover,.cti-edge-mascot[data-art="true"]:focus-visible { filter:drop-shadow(0 6px 16px #0004) drop-shadow(0 0 12px color-mix(in srgb,var(--cti-mascot-accent) 60%,transparent)); }
      .cti-edge-mascot[data-edge="left"]:not([data-art="true"]) { border-radius:0 16px 16px 0; }
      .cti-edge-mascot[data-edge="left"]:hover,.cti-edge-mascot[data-edge="left"]:focus-visible { transform:translateX(3px) scale(1.04); }
      /* The companion carries the account gauge: one cell per reported quota
         window, so the cell count itself states how many independent limits
         are in force. An account reporting a five-hour and a weekly window
         gets two cells; one reporting a single window gets one. Each cell
         fills with its own window's remaining share, so an untouched
         five-hour limit can no longer hide a weekly one close to spent. */
      /* The gauge sits outside the artwork's box for a bitmap companion, and it
         stays inside the button's hit area there, so sweeping from the
         character onto it does not count as leaving the companion. */
      .cti-edge-mascot [data-gauge] {
        position:absolute; top:50%; transform:translateY(-50%);
        display:flex; flex-direction:column; gap:4px; width:7px;
      }
      .cti-edge-mascot [data-gauge] .cti-gauge-cell {
        position:relative; display:block; box-sizing:border-box;
        width:7px; height:17px; border-radius:4px; overflow:hidden;
        background:color-mix(in srgb,CanvasText 14%,transparent);
        box-shadow:inset 0 0 0 1px color-mix(in srgb,CanvasText 9%,transparent);
      }
      .cti-edge-mascot [data-gauge] .cti-gauge-cell i {
        position:absolute; left:0; bottom:0; display:block; width:100%;
        background:var(--cti-gauge-color,var(--cti-mascot-accent));
        border-radius:3px; transition:height .3s ease;
      }
      /* No reading yet: an outlined empty slot, never a full one. A gauge that
         defaults to full reports a healthy account while knowing nothing. */
      .cti-edge-mascot [data-gauge][data-state="empty"] .cti-gauge-cell {
        background:transparent; box-shadow:none;
        border:1px dashed color-mix(in srgb,CanvasText 34%,transparent);
      }
      /* A reached window stops the account even while the other still has
         headroom, which a pair of healthy fills cannot express on its own. */
      .cti-edge-mascot [data-gauge][data-blocked="true"] .cti-gauge-cell {
        background:color-mix(in srgb,var(--cti-low) 16%,transparent);
        box-shadow:inset 0 0 0 1.5px color-mix(in srgb,var(--cti-low) 72%,transparent);
      }
      /* The tint alone reads as "low but still going", which is exactly the
         misreading the AND gate invites: one spent window stops the account
         while the other still shows headroom. A bar across the cells says
         stopped, and says it without waiting for a hover. */
      .cti-edge-mascot [data-gauge][data-blocked="true"]::after {
        content:''; position:absolute; left:-2px; right:-2px; top:50%;
        height:2px; margin-top:-1px; border-radius:2px; background:var(--cti-low);
      }
      .cti-edge-mascot[data-edge="left"] [data-gauge] { right:-3px; }
      .cti-edge-mascot[data-edge="right"] [data-gauge] { left:-3px; }
      /* With the plate gone the gauge has to clear the artwork itself rather
         than the plate's padding, or it lands on top of the character. */
      .cti-edge-mascot[data-art="true"][data-edge="right"] [data-gauge] { left:-10px; }
      .cti-edge-mascot[data-art="true"][data-edge="left"] [data-gauge] { right:-10px; }
      /* Context belongs to the current conversation, not to the account
         limits, so it wraps the companion instead of becoming a third cell.
         The 90-degree opening faces the gauge and leaves the artwork free to
         keep "holding" it. The same geometry is mirrored at the left wall. */
      .cti-edge-mascot [data-context-ring] {
        position:absolute; z-index:0; top:3px; left:50%; width:42px; height:42px;
        border-radius:50%; pointer-events:none; opacity:.16; filter:blur(.45px);
        background:conic-gradient(from 315deg,var(--cti-context-color) 0 var(--cti-context-sweep),transparent var(--cti-context-sweep) 360deg);
        -webkit-mask:radial-gradient(farthest-side,transparent calc(100% - 2px),#000 calc(100% - 1.5px));
        mask:radial-gradient(farthest-side,transparent calc(100% - 2px),#000 calc(100% - 1.5px));
        transform:translateX(-50%); transition:opacity .2s ease,filter .2s ease;
      }
      .cti-edge-mascot[data-edge="left"] [data-context-ring] { transform:translateX(-50%) scaleX(-1); }
      .cti-edge-mascot[data-art="true"] [data-context-ring] {
        top:var(--cti-ring-top); left:var(--cti-ring-left);
        width:var(--cti-ring-size); height:var(--cti-ring-size); transform:none;
      }
      .cti-edge-mascot[data-art="true"][data-edge="left"] [data-context-ring] {
        left:auto; right:var(--cti-ring-left); transform:scaleX(-1);
      }
      .cti-edge-mascot [data-context-ring][data-tone="watch"] { opacity:.62; filter:none; }
      .cti-edge-mascot [data-context-ring][data-tone="high"] { opacity:1; filter:drop-shadow(0 0 3px color-mix(in srgb,var(--cti-context-color) 58%,transparent)); }
      .cti-edge-mascot [data-context-ring][data-tone="unknown"] { display:none; }
      .cti-hud, .cti-hud * { -webkit-app-region:no-drag !important; }
      .cti-hud-head, .cti-hud-body { zoom:var(--cti-scale,1); }
      .cti-hud [data-resize] { position:absolute;width:14px;height:14px;touch-action:none;z-index:5;opacity:0;background:none;border:0; }
      .cti-hud [data-resize="nw"] { left:0;top:0;cursor:nwse-resize; }
      .cti-hud [data-resize="ne"] { right:0;top:0;cursor:nesw-resize; }
      .cti-hud [data-resize="sw"] { left:0;bottom:0;cursor:nesw-resize; }
      .cti-hud [data-resize="se"] { right:0;bottom:0;cursor:nwse-resize; }
      .cti-hud [data-resize]:focus-visible { opacity:1;outline:1px solid currentColor; }
      .cti-hud button {
        display: inline-grid;
        place-items: center;
        width: 28px;
        height: 24px;
        border: 1px solid transparent;
        border-radius: 6px;
        background: transparent;
        color: inherit;
        font: 15px/1 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        cursor: pointer;
        position: relative;
        z-index: 1;
      }
      .cti-hud-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 12px 16px;
        border-bottom: 1px solid color-mix(in srgb, CanvasText 7%, transparent);
        font-weight: 650;
        cursor: move;
        touch-action: none;
        /* The panel is its own scroll container, so the title row has to be
           pinned: otherwise the quota readout and the window controls scroll
           out of reach the moment the detail list grows past the viewport. */
        position: sticky;
        top: 0;
        z-index: 3;
        background: Canvas;
      }
      [data-cti-title] {
        cursor: pointer;
      }
      .cti-hud [data-cti-title] { width:auto; height:auto; display:flex; gap:8px; text-align:left; font:inherit; font-weight:650; padding:0; }
      [data-cti-title]::before { content:''; width:7px; height:7px; flex:none; border-radius:50%; background:var(--cti-tone); }
      .cti-hud button:hover { background:color-mix(in srgb,CanvasText 6%,transparent); }
      .cti-hud [data-tone="safe"], .cti-hud[data-tone="safe"] { --cti-tone:var(--cti-safe); }
      .cti-hud [data-tone="watch"], .cti-hud[data-tone="watch"] { --cti-tone:var(--cti-watch); }
      .cti-hud [data-tone="low"], .cti-hud[data-tone="low"] { --cti-tone:var(--cti-low); }
      .cti-hud [data-tone="unknown"], .cti-hud[data-tone="unknown"] { --cti-tone:color-mix(in srgb,CanvasText 55%,transparent); }
      .cti-status { display:inline-flex; width:fit-content; align-items:center; gap:5px; font-size:10px; font-weight:550; color:var(--cti-tone); background:color-mix(in srgb,var(--cti-tone) 8%,transparent); padding:3px 7px; border-radius:6px; }
      .cti-hud .cti-quota-value { color:var(--cti-tone); font-size:22px; line-height:1.1; letter-spacing:-.7px; }
      .cti-quota-value small { font-size:12px; margin-left:2px; font-weight:450; }
      .cti-hud [data-settings] { border-top:1px solid color-mix(in srgb,CanvasText 8%,transparent); padding-top:10px; }
      .cti-setting { display:flex; align-items:center; justify-content:space-between; gap:8px; margin:10px 0; font-size:11px; }
      .cti-setting input { accent-color:var(--cti-safe); width:14px; height:14px; }
      [data-update] { margin:8px 0; }
      .cti-update-row { display:flex; align-items:center; gap:7px; font-size:11px; }
      .cti-update-row strong { font-weight:650; }
      .cti-update-badge {
        display:inline-flex; align-items:center; gap:5px;
        font-size:10px; font-weight:600; letter-spacing:.2px;
        color:var(--cti-safe); background:color-mix(in srgb,var(--cti-safe) 12%,transparent);
        padding:3px 8px; border-radius:999px;
      }
      .cti-update-badge::before { content:''; width:6px; height:6px; border-radius:50%; background:var(--cti-safe); }
      .cti-hud .cti-text-button { width:auto; font:inherit; padding:4px 7px; background:color-mix(in srgb,CanvasText 4%,transparent); }
      .cti-hud [hidden] { display:none !important; }
      .cti-hud-tools {
        display: inline-flex;
        align-items: center;
        gap: 5px;
      }
      .cti-unit-group {
        display: inline-flex;
        align-items: center;
        gap: 2px;
        border: 1px solid color-mix(in srgb, CanvasText 12%, transparent);
        border-radius: 6px;
        padding: 2px;
        background: color-mix(in srgb, CanvasText 4%, transparent);
      }
      .cti-hud .cti-unit-button {
        width: auto;
        min-width: 30px;
        height: 20px;
        padding: 0 6px;
        border: 0;
        border-radius: 4px;
        background: transparent;
        font: 11px/1 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      }
      .cti-hud .cti-unit-button[data-active="true"] {
        background: color-mix(in srgb, CanvasText 12%, transparent);
      }
      .cti-preset-group { display:inline-flex; gap:2px; padding:2px; border-radius:7px; background:color-mix(in srgb,CanvasText 4%,transparent); border:1px solid color-mix(in srgb,CanvasText 10%,transparent); }
      .cti-hud .cti-preset-button { width:auto; min-width:34px; height:21px; padding:0 6px; border:0; border-radius:5px; font:11px/1 system-ui; }
      .cti-hud .cti-preset-button[data-active="true"] { background:color-mix(in srgb,var(--cti-tone) 16%,transparent); color:var(--cti-tone); }
      .cti-skin-group { display:grid; grid-template-columns:repeat(auto-fit,minmax(72px,1fr)); gap:4px; margin:8px 0 12px; }
      .cti-hud .cti-skin-button { width:100%; height:58px; padding:3px 1px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:1px; border:1px solid color-mix(in srgb,CanvasText 9%,transparent); border-radius:9px; background:color-mix(in srgb,CanvasText 3%,transparent); }
      .cti-hud .cti-skin-button svg { width:29px; height:34px; flex:none; }
      .cti-hud .cti-skin-button img.cti-skin-art { height:38px; width:auto; max-width:100%; object-fit:contain; flex:none; }
      .cti-hud .cti-skin-button small { max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font:8px/1 system-ui; opacity:.65; }
      .cti-hud .cti-skin-button[data-active="true"] { border-color:var(--cti-safe); background:color-mix(in srgb,var(--cti-safe) 12%,transparent); box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--cti-safe) 30%,transparent); }
      .cti-hud[data-dragging="true"] {
        transition: none;
        opacity: 0.92;
      }
      .cti-hud-body {
        display: grid;
        overflow: auto;
        min-height: 0;
        gap: 14px;
        padding: 4px 16px 14px;
        color: color-mix(in srgb, CanvasText 78%, transparent);
        font-family: inherit;
        white-space: normal;
      }
      /* The first line of the quota block answers the question the panel exists
         for - whether the account can carry what is ahead. The per-window
         shares below it are the detail, not the headline. */
      .cti-quota-budget { font-size:13px; font-weight:550; color:var(--cti-tone); padding-top:10px; }
      .cti-quota-window { padding:13px 0 0; }
      .cti-quota-window + .cti-quota-window { margin-top:5px; }
      [data-context] { border-top:1px solid color-mix(in srgb,CanvasText 8%,transparent); padding-top:12px; }
      [data-details] summary, [data-skins] summary { cursor:pointer; font-size:11px; opacity:.7; padding:4px 0; }
      [data-details][open] > div, [data-skins][open] > div { margin-top:10px; }
      /* Collapsed, the skin picker still has to say which companion is live,
         otherwise the section hides the only thing it was asked about. The
         summary keeps its default list-item display so its disclosure triangle
         matches the usage-details disclosure above it. */
      [data-skins] summary em { font-style:normal; font-weight:650; color:var(--cti-safe); opacity:1; }
      [data-explanation] { line-height:1.7; }
      .cti-hud { max-height:calc(100vh - 24px); }
      .cti-line { display:flex; justify-content:space-between; align-items:center; gap:8px; }
      .cti-muted { color:color-mix(in srgb,CanvasText 62%,Canvas); font-size:11px; }
      .cti-value { font-variant-numeric:tabular-nums; font-weight:600; color:CanvasText; }
      .cti-meter { height:5px; border-radius:4px; overflow:hidden; background:color-mix(in srgb,var(--cti-tone) 10%,transparent); margin:10px 0 8px; }
      .cti-meter span { display:block; height:100%; border-radius:inherit; background:var(--cti-tone); transition:width .18s ease, background-color .18s ease; }
      @media (prefers-reduced-motion: reduce) { .cti-meter span,.cti-hud,.cti-edge-mascot { transition:none; } }
      .cti-metrics { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:8px; }
      .cti-metric { padding:10px; border-radius:10px; background:color-mix(in srgb,CanvasText 4%,transparent); }
      .cti-metric .cti-value { display:block; font-size:16px; overflow-wrap:anywhere; letter-spacing:-.5px; margin-top:4px; }
      .cti-account-quota { font-size:11px; opacity:.65; border-top:1px solid color-mix(in srgb,CanvasText 8%,transparent); padding-top:10px; }
      .cti-source-row { display:flex; gap:5px; align-items:center; min-height:18px; }
      .cti-trust { display:inline-flex; align-items:center; padding:2px 6px; border-radius:999px; font:600 9px/1.25 system-ui; letter-spacing:.15px; }
      .cti-trust[data-kind="official"] { color:#2457a7; background:color-mix(in srgb,#3b82f6 14%,transparent); }
      .cti-trust[data-kind="local"] { color:var(--cti-safe); background:color-mix(in srgb,var(--cti-safe) 14%,transparent); }
      .cti-trust[data-kind="estimate"] { color:#8a5700; background:color-mix(in srgb,#f59e0b 18%,transparent); }
      .cti-hud[data-collapsed="true"] { width:max-content; overflow:hidden; }
      .cti-hud[data-collapsed="true"] .cti-hud-head { padding:9px 12px; border:0; gap:10px; }
      .cti-hud[data-collapsed="true"] [data-cti-title]::before { display:none; }
      .cti-mini { display:flex; gap:7px; align-items:center; padding:2px 0; }
      .cti-mini + .cti-mini { border-left:1px solid color-mix(in srgb,CanvasText 9%,transparent); padding-left:10px; }
      .cti-battery { display:block; position:relative; width:9px; height:30px; flex:none; border-radius:3px; background:color-mix(in srgb,var(--cti-tone) 15%,transparent); overflow:hidden; box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--cti-tone) 18%,transparent); }
      .cti-battery i { position:absolute; bottom:0; left:0; width:100%; background:var(--cti-tone); border-radius:2px; min-height:2px; }
      .cti-mini-copy { display:flex; flex-direction:column; gap:3px; }
      .cti-mini-copy small { font:9px/1 system-ui; color:color-mix(in srgb,CanvasText 65%,Canvas); white-space:nowrap; }
      .cti-mini-copy strong { font:650 14px/1 system-ui; font-variant-numeric:tabular-nums; color:var(--cti-tone); }
      .cti-mini-copy em { font:9px/1 system-ui; color:color-mix(in srgb,CanvasText 60%,Canvas); white-space:nowrap; }
      [data-health] { padding:10px 12px; border-radius:10px; background:color-mix(in srgb,var(--cti-watch) 5%,Canvas); font-size:11px; line-height:1.7; }
      [data-health][data-warning="true"] { background:color-mix(in srgb,var(--cti-low) 8%,Canvas); }
      .cti-hud[data-collapsed="true"] [data-settings-toggle], .cti-hud[data-collapsed="true"] [data-refresh] { display:none; }
      .cti-hud button:focus-visible { outline:2px solid CanvasText; outline-offset:2px; }
      .cti-credit {
        margin-top: 3px;
        justify-self: end;
        text-align: right;
        color: color-mix(in srgb, CanvasText 44%, transparent);
        font: 10px/1.2 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
      }
      .cti-hud[data-collapsed="true"] .cti-hud-body { display: none; }
      .cti-hud[data-collapsed="true"] .cti-unit-group { display: none; }
      .cti-reply-footer {
        margin-top: 8px;
        padding: 6px 8px;
        border: 1px solid color-mix(in srgb, CanvasText 12%, transparent);
        border-radius: 6px;
        background: color-mix(in srgb, CanvasText 5%, transparent);
        color: color-mix(in srgb, CanvasText 68%, transparent);
        font: 11px/1.35 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        overflow-wrap: anywhere;
      }
      .cti-reply-chip {
        display: block;
        box-sizing: border-box;
        width: 100%;
        max-width: 100%;
        margin-top: 6px;
        padding: 4px 7px;
        border: 1px solid color-mix(in srgb, CanvasText 12%, transparent);
        border-radius: 6px;
        background: color-mix(in srgb, CanvasText 5%, transparent);
        color: color-mix(in srgb, CanvasText 62%, transparent);
        font: 11px/1.25 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        white-space: normal;
        overflow-wrap: anywhere;
      }
      .cti-sidebar-tooltip {
        position: fixed;
        z-index: 2147483647;
        max-width: min(420px, calc(100vw - 24px));
        padding: 12px 14px;
        border: 1px solid color-mix(in srgb, CanvasText 14%, transparent);
        border-radius: 8px;
        background: color-mix(in srgb, Canvas 96%, transparent);
        color: CanvasText;
        box-shadow: 0 12px 36px color-mix(in srgb, CanvasText 18%, transparent);
        backdrop-filter: blur(16px);
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        word-break: normal;
        font: 15px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        pointer-events: none;
      }
      .cti-sidebar-credit {
        display: block;
        margin-top: 8px;
        text-align: right;
        color: color-mix(in srgb, CanvasText 44%, transparent);
        font: 11px/1.2 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
      }
    `;
    if (style.textContent !== css) style.textContent = css;
  }
  function cleanOriginalTitle(value) {
    return String(value || '')
      .split(/\n{2,}(?=(?:Context|上下文)\s)/)[0]
      .replace(/\n?(?:Context|上下文)\s+[\s\S]*$/m, '')
      .trim();
  }
  function hideSidebarTooltip() {
    document.querySelector('.cti-sidebar-tooltip')?.remove();
  }
  function showSidebarTooltip(row, text) {
    hideSidebarTooltip();
    const tooltip = document.createElement('div');
    tooltip.className = 'cti-sidebar-tooltip';
    tooltip.lang = uiLanguage() === 'zh' ? 'zh-CN' : 'en';
    const content = document.createElement('div');
    content.textContent = text;
    const credit = document.createElement('span');
    credit.className = 'cti-sidebar-credit';
    credit.textContent = tr('madeBy');
    tooltip.append(content, credit);
    document.body.appendChild(tooltip);
    const rect = row.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();
    const left = Math.min(window.innerWidth - tooltipRect.width - 12, Math.max(12, rect.right + 8));
    const top = Math.min(window.innerHeight - tooltipRect.height - 12, Math.max(12, rect.top + 30));
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
  }
  function installSidebarHoverDelegation() {
    const previous = window.__codexContextTokenInspectorSidebarDelegation;
    if (previous?.version === RUNTIME_VERSION) return;
    if (previous?.mouseover) document.removeEventListener('mouseover', previous.mouseover);
    if (previous?.mouseout) document.removeEventListener('mouseout', previous.mouseout);
    const mouseover = event => {
      const row = event.target?.closest?.(`[${SIDEBAR_HOVER_ATTR}]`);
      if (!row) return;
      setTimeout(() => showSidebarTooltip(row, row.getAttribute(SIDEBAR_HOVER_ATTR) || ''), 0);
    };
    const mouseout = event => {
      const row = event.target?.closest?.(`[${SIDEBAR_HOVER_ATTR}]`);
      if (!row) return;
      if (event.relatedTarget && row.contains(event.relatedTarget)) return;
      setTimeout(hideSidebarTooltip, 0);
    };
    document.addEventListener('mouseover', mouseover);
    document.addEventListener('mouseout', mouseout);
    window.__codexContextTokenInspectorSidebarDelegation = {
      version: RUNTIME_VERSION,
      mouseover,
      mouseout,
    };
  }
  function hudMode(root) { return root.dataset.collapsed === 'true' ? 'compact' : 'expanded'; }
  function readLayout() {
    try { return JSON.parse(localStorage.getItem('cti-layout-v2') || '{}') || {}; } catch { return {}; }
  }
  function hudBase(root) {
    return hudMode(root)==='compact' ? Math.max(180, 58 + Math.max(1,root.querySelectorAll('.cti-mini').length)*78) : 292;
  }
  function saveLayout(root) { localStorage.setItem('cti-layout-v2',JSON.stringify(root.__ctiLayout)); }
  function dockSafeTop() { return Math.min(64,Math.max(8,window.innerHeight-100)); }
  function clearDockHide(root) {
    if(root.__ctiDockHideTimer)clearTimeout(root.__ctiDockHideTimer);
    root.__ctiDockHideTimer=null;
  }
  function scheduleDockHide(root) {
    clearDockHide(root);
    if(root.dataset.dockPinned==='true')return;
    root.__ctiDockHideTimer=setTimeout(()=>{
      const mascot=document.getElementById(MASCOT_ID);
      if(root.matches(':hover') || mascot?.matches(':hover'))return;
      root.dataset.revealed='false';applyStoredHudPosition(root);
    },500);
  }
  function revealDock(root, revealed=true) {
    if(root.dataset.docked!=='true')return;
    clearDockHide(root);root.dataset.revealed=String(revealed);applyStoredHudPosition(root);
  }
  function dockVerticalY(y,viewportHeight,panelHeight) {
    const top=Math.min(64,Math.max(8,viewportHeight-100));
    const bottom=Math.max(top,viewportHeight-Math.max(panelHeight,48)-8);
    return Math.max(top,Math.min(bottom,y));
  }
  function mascotDragGeometry(start,clientY,viewportHeight,panelHeight) {
    const delta=clientY-start.pointerY,moved=start.moved||Math.abs(delta)>=4;
    return {moved,y:moved?dockVerticalY(start.top+delta,viewportHeight,panelHeight):start.top};
  }
  function ensureMascot(root) {
    let mascot=document.getElementById(MASCOT_ID);
    if(mascot)return mascot;
    mascot=document.createElement('button');
    mascot.id=MASCOT_ID;mascot.className='cti-edge-mascot';mascot.type='button';
    mascot.addEventListener('pointerenter',()=>revealDock(root,true));
    mascot.addEventListener('pointerleave',()=>scheduleDockHide(root));
    mascot.addEventListener('focus',()=>revealDock(root,true));
    mascot.addEventListener('blur',()=>scheduleDockHide(root));
    mascot.addEventListener('pointerdown',event=>{
      if(event.button!==0 || root.dataset.docked!=='true')return;
      clearDockHide(root);
      mascot.__ctiGesture={pointerY:event.clientY,top:mascot.getBoundingClientRect().top,moved:false};
      mascot.setPointerCapture(event.pointerId);
    });
    mascot.addEventListener('pointermove',event=>{
      const gesture=mascot.__ctiGesture;if(!gesture)return;
      const next=mascotDragGeometry(gesture,event.clientY,innerHeight,root.getBoundingClientRect().height);
      if(!next.moved)return;
      gesture.moved=true;event.preventDefault();
      const mode=hudMode(root),previous=root.__ctiLayout[mode]||{};
      root.__ctiLayout[mode]={...previous,y:next.y};
      saveLayout(root);applyStoredHudPosition(root);
    });
    const endDrag=event=>{
      const gesture=mascot.__ctiGesture;if(!gesture)return;
      mascot.__ctiGesture=null;
      if(gesture.moved)mascot.__ctiSuppressClickUntil=performance.now()+400;
      try{mascot.releasePointerCapture(event.pointerId);}catch{}
    };
    mascot.addEventListener('pointerup',endDrag);
    mascot.addEventListener('pointercancel',endDrag);
    mascot.addEventListener('click',event=>{
      if(performance.now()<(mascot.__ctiSuppressClickUntil||0)){event.preventDefault();return;}
      const pinned=root.dataset.dockPinned!=='true';root.dataset.dockPinned=String(pinned);
      mascot.setAttribute('aria-pressed',String(pinned));revealDock(root,true);
    });
    document.body.appendChild(mascot);
    return mascot;
  }
  function applyMascotSkin(root) {
    const mascot=ensureMascot(root),id=mascotSkin(),skin=MASCOT_SKINS[id],art=mascotArt(id);
    mascot.innerHTML=mascotMarkup(id,'cti-mascot-art');mascot.dataset.skin=id;
    const image=mascot.querySelector('img');
    if(image?.complete)queueMicrotask(()=>positionContextHint(root));
    else image?.addEventListener('load',()=>positionContextHint(root),{once:true});
    mascot.dataset.art=String(!!art);
    mascot.style.setProperty('--cti-mascot-accent',skin.accent);
    const [ringX,ringY,ringSize]=skin.ring;
    mascot.style.setProperty('--cti-ring-left',`${ringX-ringSize/2}px`);
    mascot.style.setProperty('--cti-ring-top',`${ringY-ringSize/2}px`);
    mascot.style.setProperty('--cti-ring-size',`${ringSize}px`);
    // Replacing the markup above also removes the gauge, so it is re-attached
    // here, and the base label is kept on the element rather than composed
    // into the accessible name -- otherwise every redraw would append to the
    // label the previous pass had already written.
    mascot.dataset.skinLabel=`${uiLanguage()==='zh'?skin.zh:skin.en} · ${uiLanguage()==='zh'?'上下拖动调整位置，点击保持展开':'Drag vertically to move; click to pin'}`;
    applyMascotGauge(root);
    applyMascotContext(root, root.__ctiContext);
    positionContextHint(root);
  }
  function gaugeColor(tone) {
    return tone==='low'?'var(--cti-low)':tone==='watch'?'var(--cti-watch)':tone==='safe'?'var(--cti-safe)':'color-mix(in srgb,CanvasText 45%,transparent)';
  }
  function gaugeReading() {
    const quota=window.__codexContextTokenInspectorPayload?.quota||{};
    const age=quota.updatedAt?Math.max(0,Math.floor(Date.now()/1000-quota.updatedAt)):null;
    // Same freshness window the panel uses, so the gauge and the readout can
    // never disagree about whether the account figure is still current.
    const live=quota.status==='live'&&age!=null&&age<120;
    const windows=live&&Array.isArray(quota.windows)?quota.windows:[];
    return {quota,live,windows,blocked:live&&(quota.ordinaryUsageAllowed===false||!!quota.rateLimitReachedType)};
  }
  function applyMascotGauge(root) {
    // A pure update: the companion is built by ensureMascot on a skin or dock
    // change, and this must not be the thing that brings one into existence.
    const mascot=document.getElementById(MASCOT_ID);
    if(!mascot)return;
    let gauge=mascot.querySelector('[data-gauge]');
    if(!gauge){
      gauge=document.createElement('span');
      gauge.setAttribute('data-gauge','');
      gauge.setAttribute('aria-hidden','true');
      mascot.appendChild(gauge);
    }
    const {quota,live,windows,blocked}=gaugeReading();
    // The cell count is the message. An account with no reading still gets one
    // empty slot, so an absent figure reads as absent instead of vanishing.
    const readings=windows.length?windows:[null];
    gauge.dataset.cells=String(readings.length);
    gauge.dataset.state=windows.length?'live':'empty';
    gauge.dataset.blocked=String(blocked);
    const html=readings.map(item=>{
      if(!item)return '<span class="cti-gauge-cell"></span>';
      // A reached limit is a state, not a magnitude. Filling each cell with its
      // own remaining share renders the exact case the AND gate creates - one
      // window spent, the other still holding - as "partly usable", so under a
      // block the cells go flat and the bar across them carries the state.
      if(blocked)return `<span class="cti-gauge-cell" style="--cti-gauge-color:${gaugeColor('low')}"></span>`;
      return `<span class="cti-gauge-cell" style="--cti-gauge-color:${gaugeColor(quotaTone(item.remaining))}"><i style="height:${Math.max(0,Math.min(100,Number(item.remaining)||0))}%"></i></span>`;
    }).join('');
    if(gauge.innerHTML!==html)gauge.innerHTML=html;
    const zh=uiLanguage()==='zh';
    // The pill has no room for text, so the numbers live in the accessible
    // name and the hover title, which is the same place the skin is named.
    const parts=windows.map(item=>`${windowLabel(item,true)} ${Math.round(item.remaining)}%`);
    if(Number.isFinite(Number(root.__ctiContext)))parts.push(`CTX ${Math.round(Number(root.__ctiContext))}%`);
    if(!live)parts.push(quota.status==='loading'?(zh?'正在读取配额…':'Reading quota…'):(zh?'配额暂不可用':'Quota unavailable'));
    if(blocked){
      // The reset countdown is the only actionable part of a block, and the
      // accessible name is the one channel with room for it.
      const reset=nearestResetText(windows);
      parts.push(`${zh?'已达上限':'Limit reached'}${reset?(zh?`，${reset} 重置`:` · resets ${reset}`):(zh?'，等待重置':'')}`);
    }
    const label=[mascot.dataset.skinLabel,parts.join(' · ')].filter(Boolean).join(' · ');
    mascot.setAttribute('aria-label',label);mascot.title=label;
  }
  function applyMascotContext(root, used) {
    const mascot=document.getElementById(MASCOT_ID);
    if(!mascot)return;
    let ring=mascot.querySelector('[data-context-ring]');
    if(!ring){ring=document.createElement('span');ring.setAttribute('data-context-ring','');ring.setAttribute('aria-hidden','true');mascot.prepend(ring);}
    const value=Number(used),known=Number.isFinite(value);
    const percent=known?Math.max(0,Math.min(100,value)):0;
    ring.dataset.tone=!known?'unknown':percent>=85?'high':percent>=70?'watch':'quiet';
    ring.style.setProperty('--cti-context-sweep',`${percent*2.7}deg`);
    ring.style.setProperty('--cti-context-color','light-dark(#b85b18,#f0a15a)');
    applyMascotGauge(root);
  }
  function undockHud(root) {
    if(!root.__ctiLayout)return;
    const mode=hudMode(root),previous=root.__ctiLayout[mode]||{},rect=root.getBoundingClientRect();
    root.__ctiLayout[mode]={...previous,x:Math.max(8,Math.min(innerWidth-rect.width-8,rect.left)),y:Math.max(dockSafeTop(),Math.min(innerHeight-rect.height-8,rect.top))};
    delete root.__ctiLayout[mode].edge;
    delete root.dataset.docked;delete root.dataset.dockEdge;delete root.dataset.revealed;delete root.dataset.dockPinned;
    const mascot=document.getElementById(MASCOT_ID);if(mascot)mascot.dataset.visible='false';
    saveLayout(root);
  }
  function dockCandidate(x,y,width,height) {
    if(!edgeDockEnabled())return null;
    // Only the side walls dock. The companion art is rendered as a figure
    // peeking in from a vertical edge, so a top or bottom dock would have to
    // lay the character on its side.
    const edges=[['left',Math.abs(x-8)],['right',Math.abs(innerWidth-8-(x+width))]];
    const [edge,distance]=edges.sort((a,b)=>a[1]-b[1])[0];
    return distance<=14?edge:null;
  }
  function applyDockPosition(root,wanted,edge) {
    const mascot=ensureMascot(root),topMin=dockSafeTop(),rect=root.getBoundingClientRect();
    root.dataset.docked='true';root.dataset.dockEdge=edge;
    if(!root.dataset.revealed)root.dataset.revealed='false';
    mascot.dataset.visible='true';mascot.dataset.edge=edge;applyMascotSkin(root);
    const revealed=root.dataset.revealed==='true';
    // The companion is pinned with left/right instead of a computed offset, so
    // its cut edge stays flush no matter how wide the skin's artwork is. The
    // panel clears the tallest companion plus its shadow.
    mascot.style.left=edge==='left'?'0px':'auto';
    mascot.style.right=edge==='right'?'0px':'auto';
    const y=dockVerticalY(Number.isFinite(wanted.y)?wanted.y:topMin,innerHeight,rect.height);
    const gap=52;
    mascot.style.top=`${y}px`;
    root.style.left=edge==='left'?(revealed?`${gap}px`:`${-rect.width-2}px`):(revealed?`${innerWidth-rect.width-gap}px`:`${innerWidth+2}px`);
    root.style.top=`${y}px`;
    positionContextHint(root);
  }
  function applyStoredHudPosition(root) {
    if(root.__ctiGesture) return;
    if(!root.__ctiLayout) {
      root.__ctiLayout=readLayout();
      try {
        const legacy=JSON.parse(localStorage.getItem(POSITION_KEY)||'null');
        if(legacy && !root.__ctiLayout.compact)root.__ctiLayout.compact={x:legacy.left,y:legacy.top};
      }catch{}
    }
    const mode=hudMode(root), layout=root.__ctiLayout;
    const wanted=layout[mode] || layout.compact || {};
    const base=hudBase(root);
    const width=Math.max(160,Math.min(window.innerWidth-16, wanted.width || base));
    root.style.width=width+'px';
    root.style.setProperty('--cti-scale',String(Math.max(.55,Math.min(1.65,width/base))));
    root.style.maxHeight=Math.max(80,window.innerHeight-80)+'px';
    root.style.right='auto';root.style.bottom='auto';
    const topMin=dockSafeTop();
    const rect=root.getBoundingClientRect();
    const storedEdge=wanted.edge;
    if(edgeDockEnabled() && (storedEdge==='left' || storedEdge==='right')) { applyDockPosition(root,wanted,storedEdge); return; }
    // Layouts written by builds that could also dock to the top and bottom
    // walls would otherwise restore an edge this build no longer renders, so
    // they fall back to a free-floating panel and the stored edge is dropped.
    if(storedEdge && layout[mode]) { delete layout[mode].edge; saveLayout(root); }
    delete root.dataset.docked;delete root.dataset.dockEdge;delete root.dataset.revealed;
    const mascot=document.getElementById(MASCOT_ID);if(mascot)mascot.dataset.visible='false';
    const x=Number.isFinite(wanted.x)?wanted.x:14;
    const y=Number.isFinite(wanted.y)?wanted.y:window.innerHeight-rect.height-16;
    root.style.left=Math.max(8,Math.min(window.innerWidth-rect.width-8,x))+'px';
    root.style.top=Math.max(topMin,Math.min(window.innerHeight-rect.height-8,y))+'px';
    root.querySelectorAll('[data-resize][role="slider"]').forEach(handle=>handle.setAttribute('aria-valuenow',String(Math.round(width))));
    positionContextHint(root);
  }
  function layoutPreset() {
    const value=localStorage.getItem(LAYOUT_PRESET_KEY);
    return ['mini','standard','large'].includes(value) ? value : 'standard';
  }
  function presetWidth(root, preset) {
    const ratio={mini:.82,standard:1,large:1.2}[preset] || 1;
    return Math.round(Math.max(180,Math.min(600,hudBase(root)*ratio)));
  }
  function syncExpandedAnchor(root, x, y) {
    const previous=root.__ctiLayout.expanded || {};
    root.__ctiLayout.expanded={...previous,x,y};
  }
  function updatePresetButtons(root) {
    const active=layoutPreset();
    root.querySelectorAll('[data-layout-preset]').forEach(button=>{
      const selected=button.getAttribute('data-layout-preset')===active;
      button.setAttribute('data-active',String(selected));
      button.setAttribute('aria-pressed',String(selected));
    });
  }
  function setLayoutPreset(root, preset) {
    if(!['mini','standard','large'].includes(preset))return;
    localStorage.setItem(LAYOUT_PRESET_KEY,preset);
    const mode=hudMode(root), rect=root.getBoundingClientRect(), previous=root.__ctiLayout[mode] || {};
    root.__ctiLayout[mode]={...previous,x:Number.isFinite(previous.x)?previous.x:rect.left,y:Number.isFinite(previous.y)?previous.y:rect.top,width:presetWidth(root,preset)};
    saveLayout(root);updatePresetButtons(root);applyStoredHudPosition(root);
  }
  function resizeGeometry(start,clientX,clientY,corner,viewportWidth) {
    const horizontal=(clientX-start.x)*(corner.includes('e')?1:-1);
    const vertical=(clientY-start.y)*(corner.includes('s')?1:-1);
    const delta=Math.abs(horizontal)>=Math.abs(vertical)?horizontal:vertical;
    const maxWidth=corner.includes('w')?start.right-8:viewportWidth-start.left-8;
    const width=Math.max(180,Math.min(600,maxWidth,start.width+delta));
    return {left:corner.includes('w')?start.right-width:start.left,width};
  }
  function installHudDrag(root) {
    if(root.__ctiDragInstalled)return;
    root.__ctiDragInstalled=true;
    root.__ctiApplyPosition=()=>applyStoredHudPosition(root);
    root.__ctiRevealDock=()=>{root.dataset.dockPinned='true';revealDock(root,true);};
    const handles=['nw','ne','sw','se'].map(corner=>{
      const handle=document.createElement('div');handle.dataset.resize=corner;
      if(corner==='se'){
        handle.tabIndex=0;handle.setAttribute('role','slider');
        handle.setAttribute('aria-label',uiLanguage()==='zh'?'调整面板大小':'Resize panel');
        handle.setAttribute('aria-valuemin','180');handle.setAttribute('aria-valuemax','600');
        handle.setAttribute('aria-valuenow',String(Math.round(root.getBoundingClientRect().width)));
      }
      root.appendChild(handle);return handle;
    });
    root.addEventListener('pointerenter',()=>clearDockHide(root));
    root.addEventListener('pointerleave',()=>scheduleDockHide(root));
    root.addEventListener('keydown',event=>{
      if(event.key==='Escape' && root.dataset.docked==='true'){
        root.dataset.dockPinned='false';document.getElementById(MASCOT_ID)?.setAttribute('aria-pressed','false');revealDock(root,false);
      }
    });
    function persist(x,y,width) {
      const mode=hudMode(root);const previous=root.__ctiLayout[mode] || {};
      root.__ctiLayout[mode]={...previous,x,y,...(width?{width}:{})};
      saveLayout(root);
    }
    // A pointerdown on the scrollbar gutter belongs to the scroll container.
    // Once the whole panel is a grab surface the two would otherwise fight
    // over the same gesture and the panel would move instead of scrolling.
    function isOverScrollbar(node,event) {
      if(node.scrollHeight<=node.clientHeight)return false;
      return event.clientX>=node.getBoundingClientRect().left+node.clientWidth;
    }
    root.addEventListener('pointerdown',event=>{
      if(event.button!==0)return;
      const resize=event.target.closest('[data-resize]')?.dataset.resize||null;
      // The panel body drags the panel too, not just the title row, so the
      // gesture has to skip every control that owns the pointer itself.
      const control=event.target.closest('button,input,select,textarea,summary,a,label');
      if(!resize && control && !event.target.closest('[data-cti-title]'))return;
      if(!resize && isOverScrollbar(root,event))return;
      if(!resize && root.dataset.docked==='true')undockHud(root);
      const rect=root.getBoundingClientRect();
      root.__ctiGesture={resize,x:event.clientX,y:event.clientY,left:rect.left,top:rect.top,right:rect.right,width:rect.width,moved:false};
      root.setPointerCapture(event.pointerId);
    },true);
    const move=event=>{
      const g=root.__ctiGesture;if(!g)return;
      const dx=event.clientX-g.x,dy=event.clientY-g.y;
      if(Math.abs(dx)+Math.abs(dy)<4 && !g.moved)return;
      g.moved=true;event.preventDefault();
      root.dataset.dragging='true';
      if(g.resize) {
        const resized=resizeGeometry(g,event.clientX,event.clientY,g.resize,window.innerWidth);
        persist(resized.left,g.top,resized.width);
      } else {
        const x=g.left+dx,y=g.top+dy;persist(x,y);
        g.candidate=dockCandidate(x,y,g.width,root.getBoundingClientRect().height);
        if(g.candidate)root.dataset.snapEdge=g.candidate;else delete root.dataset.snapEdge;
      }
      root.__ctiGesture=null;applyStoredHudPosition(root);root.__ctiGesture=g;
    };
    window.addEventListener('pointermove',move,true);
    function end(event) {
      const g=root.__ctiGesture;if(!g)return;
      root.__ctiGesture=null;delete root.dataset.dragging;
      delete root.dataset.snapEdge;
      if(g.moved)root.__ctiSuppressClickUntil=performance.now()+400;
      try{root.releasePointerCapture(event.pointerId);}catch{}
      applyStoredHudPosition(root);
      // A compact move is the user's canonical anchor. Keep the expanded
      // detail panel attached to that point instead of reviving an older
      // expanded coordinate from before the compact panel was moved.
      if(g.moved && !g.resize && hudMode(root)==='compact'){
        const actual=root.getBoundingClientRect();
        const compact=root.__ctiLayout.compact || {};
        root.__ctiLayout.compact={...compact,x:actual.left,y:actual.top};
        syncExpandedAnchor(root,actual.left,actual.top);
        saveLayout(root);
      }
      if(g.moved && !g.resize && g.candidate) {
        const mode=hudMode(root),actual=root.getBoundingClientRect(),previous=root.__ctiLayout[mode]||{};
        root.__ctiLayout[mode]={...previous,x:actual.left,y:actual.top,edge:g.candidate};
        root.dataset.revealed='false';root.dataset.dockPinned='false';saveLayout(root);applyStoredHudPosition(root);
      }
    }
    window.addEventListener('pointerup',end,true);
    window.addEventListener('pointercancel',end,true);
    handles[3].addEventListener('keydown',event=>{
      if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;
      event.preventDefault();
      const r=root.getBoundingClientRect();
      persist(r.left,r.top,Math.max(180,Math.min(600,r.width+(['ArrowLeft','ArrowDown'].includes(event.key)?-12:12))));
      applyStoredHudPosition(root);
    });
    const resize=()=>applyStoredHudPosition(root);
    window.addEventListener('resize',resize);
    root.__ctiRemoveResize=()=>{window.removeEventListener('resize',resize);window.removeEventListener('pointermove',move,true);window.removeEventListener('pointerup',end,true);window.removeEventListener('pointercancel',end,true);};
  }
  function keepTogglePosition(root, update) {
    const beforeMode=hudMode(root);
    const r=root.getBoundingClientRect();
    if(!root.__ctiLayout[beforeMode])root.__ctiLayout[beforeMode]={x:r.left,y:r.top};
    if(beforeMode==='compact')syncExpandedAnchor(root,r.left,r.top);
    update();
    const afterMode=hudMode(root);
    if(!root.__ctiLayout[afterMode])root.__ctiLayout[afterMode]={x:r.left,y:r.top};
    saveLayout(root);applyStoredHudPosition(root);
  }
  function updateUnitButtons(root) {
    root.querySelectorAll('[data-cti-unit]').forEach(button => {
      button.setAttribute('data-active', String(button.getAttribute('data-cti-unit') === unitMode()));
    });
    updatePresetButtons(root);
    updateSkinButtons(root);
  }
  function updateHudLanguage(root) {
    const language = uiLanguage();
    const htmlLanguage = language === 'zh' ? 'zh-CN' : 'en';
    if (root.lang !== htmlLanguage) root.lang = htmlLanguage;
    const unitGroup = root.querySelector('.cti-unit-group');
    if (unitGroup?.getAttribute('aria-label') !== tr('tokenUnit')) {
      unitGroup?.setAttribute('aria-label', tr('tokenUnit'));
    }
    const rawButton = root.querySelector('[data-cti-unit="raw"]');
    if (rawButton && rawButton.textContent !== tr('rawUnit')) rawButton.textContent = tr('rawUnit');
    const toggle = root.querySelector('[data-cti-toggle]');
    const toggleLabel = root.getAttribute('data-collapsed') === 'true' ? tr('expandMonitor') : tr('collapseMonitor');
    if (toggle?.getAttribute('aria-label') !== toggleLabel) toggle?.setAttribute('aria-label', toggleLabel);
  }
  function ensureHud() {
    let root = document.getElementById(ROOT_ID);
    if (root) {
      applyStoredHudPosition(root);
      installHudDrag(root);
      updateUnitButtons(root);
      updateHudLanguage(root);
      return root;
    }
    root = document.createElement('section');
    root.id = ROOT_ID;
    root.className = 'cti-hud';
    root.setAttribute('data-collapsed', localStorage.getItem(COLLAPSE_KEY) === 'true' ? 'true' : 'false');
    root.innerHTML = `
      <div class="cti-hud-head">
        <button type="button" data-cti-title>Monitor</button>
        <div class="cti-hud-tools">
          <div class="cti-unit-group" aria-label="Token unit">
            <button class="cti-unit-button" type="button" data-cti-unit="auto">${uiLanguage()==='zh'?'自动':'Auto'}</button>
            <button class="cti-unit-button" type="button" data-cti-unit="raw">raw</button>
            <button class="cti-unit-button" type="button" data-cti-unit="k">K</button>
            <button class="cti-unit-button" type="button" data-cti-unit="m">M</button>
          </div>
          <button type="button" data-refresh aria-label="${uiLanguage()==='zh'?'刷新配额':'Refresh quota'}" title="${uiLanguage()==='zh'?'刷新配额':'Refresh quota'}">↻</button>
          <button type="button" data-settings-toggle aria-expanded="false" aria-label="${uiLanguage()==='zh'?'显示设置':'Display settings'}" title="${uiLanguage()==='zh'?'显示设置':'Display settings'}">⋯</button>
          <button type="button" data-cti-toggle>−</button>
        </div>
      </div>
      <div class="cti-hud-body" data-cti-body></div>
    `;
    root.querySelectorAll('[data-cti-unit]').forEach(button => {
      button.addEventListener('pointerdown', event => event.stopPropagation());
      button.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        localStorage.setItem(UNIT_KEY, button.getAttribute('data-cti-unit'));
        applyAll(window.__codexContextTokenInspectorPayload);
      });
    });
    root.querySelector('[data-refresh]').addEventListener('click', () => {
      window.__ctiRefreshRequested = true;
      root.querySelector('[data-refresh]').setAttribute('aria-label', uiLanguage()==='zh'?'已请求刷新':'Refresh requested');
      root.querySelector('[data-freshness]').textContent = uiLanguage()==='zh'?'正在刷新，约 10 秒内更新…':'Refreshing within about 10 seconds…';
    });
    root.querySelector('[data-settings-toggle]').addEventListener('click', () => {
      const panel = root.querySelector('[data-settings]');
      panel.hidden = !panel.hidden;
      root.querySelector('[data-settings-toggle]').setAttribute('aria-expanded', String(!panel.hidden));
      clampHud(root);
    });
    const titleButton = root.querySelector('[data-cti-title]');
    titleButton.addEventListener('pointerdown', event => {
      event.stopPropagation();
    });
    titleButton.addEventListener('click', event => {
      if(performance.now()<(root.__ctiSuppressClickUntil||0)){event.preventDefault();return;}
      event.preventDefault();
      event.stopPropagation();
      if (root.getAttribute('data-collapsed') === 'true') {
        toggleHud(root);
      }
    });
    const toggleButton = root.querySelector('[data-cti-toggle]');
    toggleButton.addEventListener('pointerdown', event => {
      event.stopPropagation();
    });
    toggleButton.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      if (root.__ctiSuppressToggle) {
        root.__ctiSuppressToggle = false;
        return;
      }
      toggleHud(root);
    });
    toggleButton.addEventListener('pointerup', event => {
      if (!root.__ctiSuppressToggle) return;
      event.preventDefault();
      root.__ctiSuppressToggle = false;
    });
    function toggleHud(root) {
      keepTogglePosition(root, () => {
        const next = root.getAttribute('data-collapsed') !== 'true';
        root.setAttribute('data-collapsed', String(next));
        localStorage.setItem(COLLAPSE_KEY, String(next));
        root.querySelector('[data-cti-toggle]').textContent = next ? '+' : '−';
        updateHudTitle(root);
        clampHud(root);
      });
    }
    document.body.appendChild(root);
    applyStoredHudPosition(root);
    installHudDrag(root);
    updateUnitButtons(root);
    updateHudLanguage(root);
    return root;
  }
  function applySidebar(summaries) {
    const byThread = new Map();
    summaries.forEach(item => {
      byThread.set(String(item.thread_id), item);
      (item.thread_keys || []).forEach(key => byThread.set(String(key), item));
    });
    document.querySelectorAll('[data-app-action-sidebar-thread-row]').forEach(row => {
      const id = rowThreadId(row);
      const item = byThread.get(String(id));
      if (!item) return;
      const existing = row.getAttribute('data-cti-original-title') || cleanOriginalTitle(row.getAttribute('title') || '');
      if (!row.hasAttribute('data-cti-original-title')) row.setAttribute('data-cti-original-title', existing);
      row.removeAttribute('title');
      row.setAttribute(SIDEBAR_HOVER_ATTR, summaryHover(item));
    });
  }
  function assistantNodes() {
    // Codex tasks and ChatGPT conversations currently use different turn
    // wrappers. Keep both paths so an app update can move a task between them.
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
    return nodes.filter(node => !node.closest(`#${ROOT_ID}`));
  }
  function actionRowForAssistant(node) {
    const turn = node.closest('[data-turn-key], [data-chatgpt-conversation-turn="true"]') || node;
    const sentTime = turn.querySelector('[data-assistant-message-sent-time]');
    if (sentTime?.parentElement) return sentTime.parentElement;
    const candidates = Array.from(turn.querySelectorAll('span, div')).filter(el => {
      if (el.closest(`#${ROOT_ID}`) || el.hasAttribute(CHIP_ATTR)) return false;
      const text = (el.textContent || '').trim();
      return /^Work(?:ing|ed) for /.test(text) || /\b\d{1,2}:\d{2}\s?(?:AM|PM)\b/.test(text);
    });
    const candidate = candidates.find(el => /^Work(?:ing|ed) for /.test((el.textContent || '').trim())) ||
      candidates.find(el => /\b\d{1,2}:\d{2}\s?(?:AM|PM)\b/.test((el.textContent || '').trim())) ||
      null;
    return candidate?.parentElement || null;
  }
  function assistantChipTargets() {
    const targetsByHost = new Map();
    assistantNodes().forEach(node => {
      const actionRow = actionRowForAssistant(node);
      const host = actionRow?.parentElement || node;
      if (!host) return;
      // Multi-step turns can expose several assistant wrappers for one native
      // action row. The action-row host is the visible reply boundary, so the
      // last wrapper for that host owns its single token chip.
      targetsByHost.set(host, { node, actionRow, host });
    });
    return Array.from(targetsByHost.values());
  }
  function directReplyChips(host) {
    return Array.from(host?.children || []).filter(child => child.hasAttribute(CHIP_ATTR));
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
      .map((item, index) => ({ index, prefix: normalizedText(item.textPrefix) }))
      .filter(item => item.prefix.length >= 24);
    return detail.__ctiPrefixes;
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
    if (chunkMatches >= 2 || chunkScore >= 18) return chunkScore;
    return 0;
  }
  function detailForVisiblePage(payload) {
    const nodes = assistantNodes();
    if (!nodes.length) return null;
    const signature = nodes
      .map(node => normalizedText(node.textContent).slice(0, 180))
      .join('||');
    if (
      payload.__ctiVisibleMatchCache &&
      payload.__ctiVisibleMatchCache.signature === signature &&
      payload.__ctiVisibleMatchCache.threadId
    ) {
      const cached = detailCandidates(payload).find(
        detail => String(detail.thread_id) === String(payload.__ctiVisibleMatchCache.threadId)
      );
      if (cached) return cached;
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
    payload.__ctiVisibleMatchCache = {
      signature,
      threadId: bestScore > 0 ? best?.thread_id : null,
      score: bestScore,
    };
    return bestScore > 0 ? best : null;
  }
  function applyFooters(detail) {
    if (!detail) return;
    const targets = assistantChipTargets();
    const items = detail.assistantItems || [];
    const used = new Set();
    const keptChips = new Set();
    targets.forEach(({ node, actionRow, host }, index) => {
      const item = visibleItemForNode(node, index, items, used, targets.length);
      const text = item?.footer;
      if (!text) return;
      node.querySelector(`[${FOOTER_ATTR}]`)?.remove();
      const sessionRound = item.roundIndex || index + 1;
      const sessionTotalRounds = item.totalRounds || items.length || targets.length;
      const chipText = itemChip(item, sessionRound, sessionTotalRounds);
      const directChips = directReplyChips(host);
      // A v5 chip can be outside `node` after it is moved below the native
      // buttons. Look it up from the stable host first so refreshes reuse it.
      let chip = actionRow?.nextElementSibling?.hasAttribute(CHIP_ATTR)
        ? actionRow.nextElementSibling
        : directChips[0] || node.querySelector(`[${CHIP_ATTR}]`);
      if (!chip) {
        chip = document.createElement('div');
        chip.className = 'cti-reply-chip';
        chip.setAttribute(CHIP_ATTR, 'true');
      }
      keptChips.add(chip);
      chip.lang = uiLanguage() === 'zh' ? 'zh-CN' : 'en';
      if (actionRow?.parentElement === host) {
        // Keep Codex's fixed-height action row untouched. The chip is a sibling
        // immediately below it, so buttons and timestamps retain their layout.
        if (chip.parentElement !== host || chip.previousElementSibling !== actionRow) {
          actionRow.insertAdjacentElement('afterend', chip);
        }
      } else if (chip.parentElement !== host) {
        host.appendChild(chip);
      }
      if (chip.textContent !== chipText) chip.textContent = chipText;
      const title = itemTitle(item, sessionRound, sessionTotalRounds);
      if (chip.getAttribute('title') !== title) chip.setAttribute('title', title);
    });
    // Remove duplicates created by older runtimes and chips whose virtualized
    // reply host is no longer present. This also makes repeated refreshes
    // idempotent, preventing token rows from growing the scrollable content.
    document.querySelectorAll(`[${CHIP_ATTR}]`).forEach(chip => {
      if (!keptChips.has(chip)) chip.remove();
    });
  }
  function applyHud(payload, currentDetail = null) {
    const root = ensureHud();
    const body = root.querySelector('[data-cti-body]');
    const zh = uiLanguage() === 'zh';
    // A renderer outlives plugin updates and only rebuilds the companion when
    // the skin or the dock changes, so a redrawn bitmap would never reach a
    // window that keeps the same skin selected. Rebuild it once per new
    // runtime, the same signal that tears down stale observers.
    if (runtimeChanged) applyMascotSkin(root);
    // The gauge rides on the companion, but the companion is rebuilt only when
    // the skin or the dock changes. Quota arrives on its own schedule, so the
    // gauge is refreshed on every pass or its cells freeze at the reading
    // taken when the skin last changed.
    applyMascotGauge(root);
    if (!body.querySelector('[data-quota]') || root.__ctiBodyLanguage!==uiLanguage()) {
      const units=root.querySelector('.cti-unit-group');
      root.__ctiBodyLanguage=uiLanguage();
      body.innerHTML = `
        <div data-quota></div>
        <div data-context></div>
        <div data-health></div>
        <button type="button" class="cti-text-button" data-handoff>${zh?'复制交接指令':'Copy handoff prompt'}</button>
        <details data-details><summary>${zh ? '用量详情' : 'Usage details'}</summary>
          <div class="cti-metrics" data-metrics></div>
          <div class="cti-muted" data-explanation></div>
        </details>
        <div data-settings hidden>
          <div class="cti-line"><span class="cti-muted">${zh?'显示设置':'Display settings'}</span><button class="cti-text-button" type="button" data-position-reset>${zh?'恢复位置':'Reset position'}</button></div>
          <div class="cti-setting"><span>${zh?'面板尺寸':'Panel size'}</span><div class="cti-preset-group" role="group" aria-label="${zh?'面板尺寸':'Panel size'}"><button class="cti-preset-button" type="button" data-layout-preset="mini">${zh?'迷你':'Mini'}</button><button class="cti-preset-button" type="button" data-layout-preset="standard">${zh?'标准':'Standard'}</button><button class="cti-preset-button" type="button" data-layout-preset="large">${zh?'大字':'Large'}</button></div></div>
          <label class="cti-setting"><span>${zh?'边缘软吸附':'Soft edge docking'}</span><input type="checkbox" data-edge-dock></label>
          <details data-skins>
            <summary>${zh?'角色皮肤':'Character skin'} · <em data-skin-current></em></summary>
            <div class="cti-skin-group" role="group" aria-label="${zh?'角色皮肤':'Character skin'}">${skinButtons()}</div>
          </details>
          <div class="cti-setting"><span>${zh?'数字单位':'Number format'}</span><div data-units></div></div>
          <label class="cti-setting"><span>${zh?'配额 ≤20% 时通知':'Notify at ≤20% remaining'}</span><input type="checkbox" data-alerts></label>
          <label class="cti-setting"><span>${zh?'上下文轻提醒':'Context hints'}</span><input type="checkbox" data-context-alerts></label>
          <label class="cti-setting"><span>${zh?'语言':'Language'}</span><select data-language><option value="auto">Auto</option><option value="zh">中文</option><option value="en">English</option></select></label>
          <div class="cti-muted">${zh?'每个配额窗口仅提醒一次。系统需允许通知。':'Once per quota window. System notifications must be allowed.'}</div>
          <div class="cti-setting" aria-label="${zh?'配额颜色说明':'Quota color legend'}">
            <span class="cti-status" data-tone="safe">&gt;50%</span><span class="cti-status" data-tone="watch">20–50%</span><span class="cti-status" data-tone="low">≤20%</span>
          </div>
          <div class="cti-muted" data-build></div>
          <div data-update></div>
          <div class="cti-muted" data-dom></div>
          <div class="cti-muted">${zh?'只读 · 本机 · 不上传':'Read-only · local · never uploaded'}</div>
        </div>
        <div class="cti-muted" data-freshness></div>`;
      body.querySelector('[data-units]').appendChild(units);
      const language=body.querySelector('[data-language]');language.value=localStorage.getItem('cti-language')||'auto';
      language.addEventListener('change',()=>{localStorage.setItem('cti-language',language.value);applyAll(window.__codexContextTokenInspectorPayload);});
      body.querySelectorAll('[data-layout-preset]').forEach(button=>button.addEventListener('click',()=>setLayoutPreset(root,button.getAttribute('data-layout-preset'))));
      const edgeDock=body.querySelector('[data-edge-dock]');edgeDock.checked=edgeDockEnabled();
      edgeDock.addEventListener('change',()=>{
        localStorage.setItem(EDGE_DOCK_KEY,String(edgeDock.checked));
        if(!edgeDock.checked)undockHud(root);applyStoredHudPosition(root);
      });
      body.querySelectorAll('[data-skin-choice]').forEach(button=>button.addEventListener('click',()=>{
        localStorage.setItem(SKIN_KEY,button.dataset.skinChoice);applyMascotSkin(root);updateSkinButtons(root);
      }));
      updateSkinButtons(root);
      const tips=body.querySelector('[data-context-alerts]');tips.checked=localStorage.getItem('cti-context-reminders')!=='false';
      tips.addEventListener('change',()=>localStorage.setItem('cti-context-reminders',String(tips.checked)));
      const details = body.querySelector('[data-details]');
      details.open = localStorage.getItem('cti-details-open') === 'true';
      details.addEventListener('toggle', () => {localStorage.setItem('cti-details-open', String(details.open)); clampHud(root);});
      const skins = body.querySelector('[data-skins]');
      skins.open = localStorage.getItem(SKINS_OPEN_KEY) === 'true';
      skins.addEventListener('toggle', () => {localStorage.setItem(SKINS_OPEN_KEY, String(skins.open)); clampHud(root);});
      const alerts = body.querySelector('[data-alerts]');
      body.querySelector('[data-handoff]').addEventListener('click', async event => {
        const text = uiLanguage()==='zh' ? '请为当前任务生成可直接交给新对话的交接说明：原始目标、用户约束、已完成修改与文件路径、关键决策、验证结果、未完成事项、风险及下一步命令。区分事实与假设，不包含密钥，不重复整段聊天记录。先完成交接说明，暂不继续执行新工作。' : 'Create a handoff for this task: goal, constraints, completed changes and file paths, decisions, verification, remaining work, risks and next commands. Distinguish facts from assumptions, omit secrets, and do not copy the entire chat. Produce the handoff before doing more work.';
        try { await navigator.clipboard.writeText(text); event.target.textContent=uiLanguage()==='zh'?'已复制，粘贴到当前对话生成交接':'Copied; paste into this task'; }
        catch { event.target.textContent=uiLanguage()==='zh'?'复制失败，请直接要求生成交接说明':'Copy failed; ask for a handoff'; }
      });
      alerts.checked = localStorage.getItem('cti-alerts') === 'true';
      alerts.addEventListener('change', () => localStorage.setItem('cti-alerts', String(alerts.checked)));
      body.querySelector('[data-position-reset]').addEventListener('click', () => {
        localStorage.removeItem(POSITION_KEY);
        localStorage.removeItem('cti-layout-v2');root.__ctiLayout={};
        root.style.left='14px'; root.style.top='auto'; root.style.bottom='16px';
        clampHud(root);
      });
    }
    const put = (selector, html) => {
      const node = body.querySelector(selector);
      if (node.innerHTML !== html) node.innerHTML = html;
    };
    const quota = payload.quota || {status:'loading', windows:[]};
    const age = quota.updatedAt ? Math.max(0, Math.floor(Date.now()/1000-quota.updatedAt)) : null;
    const live = quota.status === 'live' && age < 120;
    let quotaHtml = '';
    for (const item of live ? quota.windows : []) {
      const duration=windowLabel(item);
      const reset = typeof item.resetsAt === 'number' ? new Date(item.resetsAt*1000) : null;
      const minutes = reset ? Math.max(0, Math.ceil((reset.getTime()-Date.now())/60000)) : null;
      const time = reset ? reset.toLocaleString(zh ? 'zh-CN' : 'en', {month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'}) : '—';
      const countdown = minutes == null ? '' : minutes === 0 ? (zh ? '等待刷新' : 'Awaiting refresh') :
        minutes >= 1440 ? `${Math.floor(minutes/1440)}${zh ? ' 天 ' : 'd '}${Math.floor(minutes%1440/60)}h` :
        minutes < 60 ? `${minutes}${zh ? ' 分钟后' : ' min'}` :
        `${Math.floor(minutes/60)}h ${minutes%60}m`;
      const tone = quotaTone(item.remaining);
      const pace = typeof item.paceDelta === 'number' ?
        (Math.abs(item.paceDelta)<2 ? (zh?'符合均匀进度':'On steady pace') : item.paceDelta>0 ?
          `${zh?'快于均匀进度':'Ahead of pace'} ${Math.round(item.paceDelta)}pt` :
          `${zh?'慢于均匀进度':'Behind pace'} ${Math.round(Math.abs(item.paceDelta))}pt`) : '';
      const exhaust = typeof item.projectedExhaustAt === 'number' ? new Date(item.projectedExhaustAt*1000) : null;
      const forecast = exhaust ? `${zh?'按当前速度预计':'At current pace'} ${exhaust.toLocaleString(zh?'zh-CN':'en',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})} ${zh?'耗尽':'exhausted'}` : '';
      quotaHtml += `<div class="cti-quota-window" data-tone="${tone}">
        <div class="cti-line"><span>${duration}</span><span class="cti-value cti-quota-value">${Math.round(item.remaining)}<small>%</small></span></div>
        <div class="cti-meter" role="meter" aria-label="${duration}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${item.remaining}"><span style="width:${item.remaining}%"></span></div>
        <div class="cti-line" style="margin-bottom:6px"><span class="cti-status">${toneLabel(tone)}</span><span class="cti-muted">${pace}</span></div>
        <div class="cti-muted">${time} ${zh ? '重置' : 'reset'} · ${countdown}${forecast?`<br>${forecast}`:''}</div></div>`;
    }
    // The panel's own headline, spelled out: the answer the collapsed bar gives
    // in shorthand, with the shares left to the per-window lines below. A block
    // reports the reset instead, because that is the part anyone can act on.
    if (live && quota.windows.length) {
      const stoppedAccount = quota.ordinaryUsageAllowed === false || !!quota.rateLimitReachedType;
      const nearest = nearestResetText(quota.windows);
      const note = stoppedAccount
        ? `${zh?'账户已达上限':'Account at its limit'}${nearest?(zh?`，最近重置 ${nearest}`:` · nearest reset ${nearest}`):(zh?'，等待重置':'')}`
        : accountBudgetText(quota);
      if (note) {
        const constrained = Math.min(...quota.windows.map(item => item.remaining));
        const trust = stoppedAccount ? '' : `<span class="cti-trust" data-kind="estimate">${zh?'估算':'Estimate'}</span> `;
        quotaHtml = `<div class="cti-quota-budget" data-tone="${stoppedAccount?'low':quotaTone(constrained)}">${trust}${note}</div>` + quotaHtml;
      }
    }
    if (!quotaHtml) quotaHtml = `<div class="cti-muted">${quota.status==='loading' ?
      (zh?'正在读取账户配额…':'Reading quota…') : live && quota.windowStatus==='not_reported'?(zh?'账户未报告周期配额窗口':'No periodic quota windows reported'):(zh?'暂时无法读取配额':'Quota: unavailable')}</div>`;
    // A healthy short window is not permission to keep working, so the AND
    // relationship the gauge only implies gets stated once here.
    if (live && (quota.windows.length > 1 || quota.ordinaryUsageAllowed === false || quota.rateLimitReachedType)) {
      const notes = [];
      if (quota.windows.length > 1) notes.push(zh?'两个窗口均需有余量才能继续。':'Every window must have headroom to continue.');
      // The headline above reports a block whenever there is a window to report
      // it against, so this only has to say it for an account that reached a
      // limit without reporting any window at all.
      if (!quota.windows.length && (quota.ordinaryUsageAllowed === false || quota.rateLimitReachedType)) {
        notes.push(zh?'账户当前已达上限。':'The account is at its limit right now.');
      }
      if (notes.length) quotaHtml += `<div class="cti-muted">${notes.join(' ')}</div>`;
    }
    const usage=quota.usage||{};
    const usageSummary=usage.summary||{};
    const daily=Array.isArray(usage.dailyUsageBuckets)?usage.dailyUsageBuckets:[];
    const latestDay=daily.length?daily[daily.length-1]:null;
    const usageParts=[];
    if(latestDay&&typeof latestDay.tokens==='number')usageParts.push(`${zh?'最近日用量':'Latest daily'} ${token(latestDay.tokens)}`);
    if(typeof usageSummary.lifetimeTokens==='number')usageParts.push(`${zh?'累计活动':'Lifetime activity'} ${token(usageSummary.lifetimeTokens)}`);
    const resetCredits=quota.resetCredits;
    if(resetCredits&&typeof resetCredits.availableCount==='number'){
      let text=`${zh?'可用重置额度':'Reset credits'} ${resetCredits.availableCount}`;
      if(typeof resetCredits.nextExpiresAt==='number')text+=` · ${zh?'最近到期':'next expiry'} ${new Date(resetCredits.nextExpiresAt*1000).toLocaleString(zh?'zh-CN':'en',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})}`;
      usageParts.push(text);
    }
    if(usageParts.length)quotaHtml+=`<div class="cti-account-quota">${usageParts.join(' · ')}</div>`;
    quotaHtml=`<div class="cti-source-row"><span class="cti-trust" data-kind="official">${zh?'官方账户':'Official account'}</span></div>`+quotaHtml;
    put('[data-quota]', quotaHtml);
    const id = currentDetail?.thread_id || activeThreadId() || payload.activeThreadId;
    const selected = (payload.summaries || []).find(item =>
      threadKeys(id).some(key => String(item.thread_id) === key || (item.thread_keys || []).includes(key)));
    root.__ctiSessionTotalTokens = selected?.session_total_tokens;
    root.__ctiContext = selected?.latest_context_percent;
    applyMascotContext(root, root.__ctiContext);
    const health = payload.health;
    root.__ctiHealth = health;
    maybeContextHint(root, selected, health, id);
    body.querySelector('[data-health]').setAttribute('data-warning', String(health?.recommendHandoff === true));
    body.querySelector('[data-health]').title = health?.recommendHandoff ? (health.reason==='baseline' ? '建议依据：压缩后首请求仍占上下文窗口至少 40%。这是经验阈值，不是官方上限。' : '建议依据：最近两次压缩间隔均不超过 5 个不同请求。这是经验阈值。') : '压缩次数和压后首请求来自本地日志；上下文变化不等于会话累计 Token。';
    const baseline = health?.after == null ? (zh?'等待后续请求':'Awaiting next request') : `${token(health.after)} (${pct(health.afterPercent)})`;
    put('[data-health]', `<div class="cti-source-row"><span class="cti-trust" data-kind="local">${zh?'本地日志':'Local logs'}</span></div>`+(health?.count ? `${zh?'已观察压缩':'Compactions observed'} ${health.count} ${zh?'次':''}<br>${zh?'压后首请求':'First request after compression'} ${baseline}<br><span class="cti-muted">${zh?'含系统与工具，不等于摘要本身大小。':'Includes system/tools; not summary-only size.'}</span>${health.recommendHandoff?`<br><strong>${zh?'建议整理交接，换新任务继续':'Consider a handoff to a new task'}</strong>`:''}` : `<span class="cti-muted">${zh?'尚未观察到压缩事件':'No observed compaction events'}</span>`));
    if (selected) {
      body.querySelector('[data-context]').setAttribute('data-tone', contextTone(selected.latest_context_percent));
      put('[data-context]', `<div class="cti-line"><span><span class="cti-trust" data-kind="local">${zh?'本地会话':'Local session'}</span> ${zh?'上下文已用':'Context used'}</span><span class="cti-value">${pct(selected.latest_context_percent)}</span></div>
        <div class="cti-meter" role="meter" aria-label="${zh?'上下文占用':'Context used'}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.max(0,Math.min(100,selected.latest_context_percent||0))}"><span style="width:${Math.max(0,Math.min(100,selected.latest_context_percent||0))}%"></span></div>
        <div class="cti-muted">${token(selected.latest_context_tokens)} / ${token(selected.context_window)} · Token</div>`);
      put('[data-metrics]', `<div class="cti-metric"><span class="cti-muted">${tr('turn')}</span><span class="cti-value">${token(selected.latest_turn_total_tokens)}</span></div>
        <div class="cti-metric"><span class="cti-muted">${tr('session')}</span><span class="cti-value">${token(selected.session_total_tokens)}</span></div>`);
      put('[data-explanation]', `${tr('input')}: ${token(selected.latest_turn_input_tokens)} · ${tr('cachedInput')}: ${token(selected.latest_turn_cached_input_tokens)} · ${tr('output')}: ${token(selected.latest_turn_output_tokens)}<br>
        ${zh?'模型':'Model'}: ${selected.model||'—'} · ${zh?'推理强度':'Reasoning'}: ${selected.reasoning_effort||'—'}<br>
        ${zh?'缓存占比':'Cached input share'}: ${selected.latest_turn_input_tokens>0 && typeof selected.latest_turn_cached_input_tokens==='number'?pct(Math.min(100,100*selected.latest_turn_cached_input_tokens/selected.latest_turn_input_tokens)):'—'}<br>
        ${zh?'缓存已包含在输入内。会话累计不等于上下文占用；Token 不可换算为账户剩余配额。':'Cached tokens are part of input. Session totals differ from context usage. Tokens do not convert to account quota.'}`);
    } else {
      body.querySelector('[data-context]').setAttribute('data-tone', 'unknown');
      put('[data-context]', `<span class="cti-muted">${tr('noRecords')}</span>`);
      put('[data-metrics]', '');
      put('[data-explanation]', '');
    }
    const errorLabels={cli_missing:zh?'找不到 Codex CLI':'Codex CLI missing',timeout:zh?'账户读取超时':'Account read timed out',app_server:zh?'App Server 不可用':'App Server unavailable',account_unavailable:zh?'账户暂不可用':'Account unavailable'};
    // Which plan an account is on is what decides how many windows it reports,
    // so naming it here explains why the gauge has the number of cells it has.
    const plan = typeof quota.planType==='string' && quota.planType ? ` · ${quota.planType.charAt(0).toUpperCase()}${quota.planType.slice(1)}` : '';
    put('[data-freshness]', live ?
      `${zh?'账户接口':'Account'}${plan} · ${age<10?(zh?'刚刚更新':'just updated'):`${age}s ${zh?'前更新':'ago'}`}` :
      `${zh?'账户配额未更新':'Account unavailable'}${quota.errorCode?` · ${errorLabels[quota.errorCode]||quota.errorCode}`:''} · ${zh?'本地 Token 独立读取':'local tokens independent'}`);
    // The plugin version, the cachebuster Codex keys its cache directory on,
    // and the injected runtime version move independently, and a plugin cache
    // does not refresh on its own. Naming all of them here is what turns "I
    // installed it and nothing changed" into a readable fact.
    const stamp = payload.build || {};
    const stampParts = [];
    if (stamp.pluginVersion) stampParts.push(`${zh?'插件':'plugin'} ${stamp.pluginVersion}`);
    if (typeof stamp.runtimeVersion === 'number') stampParts.push(`${zh?'运行时':'runtime'} ${stamp.runtimeVersion}`);
    if (typeof stamp.installedAt === 'number') stampParts.push(`${zh?'安装于':'installed'} ${new Date(stamp.installedAt*1000).toLocaleString(zh?'zh-CN':'en',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})}`);
    put('[data-build]', stampParts.length ? stampParts.join(' · ') : (zh?'版本信息未记录':'Build information not recorded'));
    // A newer published build is the one thing a local-only monitor cannot see
    // on its own, so the check result rides in with the payload. Only an
    // available update is spoken aloud; "up to date" is a muted line and a
    // failed or in-flight check stays silent rather than nagging.
    const upd = payload.update || {};
    const updNode = body.querySelector('[data-update]');
    if (updNode) {
      if (upd.status === 'update_available' && upd.latestSemver) {
        const updHtml = `<div class="cti-update-row"><span class="cti-update-badge">${zh?'新版本可用':'Update available'}</span><strong>v${upd.latestSemver}</strong><button type="button" class="cti-text-button" data-update-open>${zh?'查看':'View'}</button></div>`;
        if (updNode.innerHTML !== updHtml) {
          updNode.innerHTML = updHtml;
          updNode.querySelector('[data-update-open]').addEventListener('click', async event => {
            const url = upd.url || 'https://github.com/ailble-abum/codex-quota-monitor/releases';
            const opened = window.open(url, '_blank', 'noopener');
            if (!opened) {
              try { await navigator.clipboard.writeText(url); event.target.textContent = zh?'链接已复制':'Link copied'; }
              catch { event.target.textContent = url; }
            }
          });
        }
      } else if (upd.status === 'up_to_date') {
        put('[data-update]', `<span class="cti-muted">${zh?'已是最新版本':'Up to date'}</span>`);
      } else {
        put('[data-update]', '');
      }
    }
    // The selectors the overlay relies on to find the active thread can drift
    // under a Codex update. Reporting which landed makes that drift visible
    // instead of silently drawing a smaller panel.
    const probe = payload.dom || {};
    const probeParts = [];
    if (typeof probe.sidebarRows === 'number') probeParts.push(`${zh?'会话':'threads'} ${probe.sidebarRows}`);
    probeParts.push(probe.activeRow ? (zh?'活动行 ✓':'active ✓') : (zh?'活动行 ✗':'active ✗'));
    probeParts.push(probe.conversationId ? (zh?'会话ID ✓':'id ✓') : (zh?'会话ID ✗':'id ✗'));
    const drift = (typeof probe.sidebarRows === 'number' && probe.sidebarRows > 0 && !probe.activeRow)
      || (typeof probe.sidebarRows === 'number' && probe.sidebarRows === 0);
    if (drift) probeParts.push(zh?'界面可能已更新':'UI may have changed');
    put('[data-dom]', `${zh?'界面探测':'DOM probe'} · ${probeParts.join(' · ')}`);
    updateHudTitle(root);
    updateUnitButtons(root);
    const toggle = root.querySelector('[data-cti-toggle]');
    toggle.textContent = root.getAttribute('data-collapsed') === 'true' ? '+' : '−';
    clampHud(root);
  }
  function clampHud(root) { applyStoredHudPosition(root); }
  function contextHintGeometry(anchor,toast,viewport,edge) {
    const beside=edge==='left'||edge==='right';
    const rawLeft=edge==='left'?anchor.right+8:edge==='right'?anchor.left-toast.width-8:anchor.left;
    const rawTop=beside?anchor.top+(anchor.height-toast.height)/2:anchor.bottom+8;
    return {
      left:Math.round(Math.max(8,Math.min(viewport.width-toast.width-8,rawLeft))),
      top:Math.round(Math.max(68,Math.min(viewport.height-toast.height-8,rawTop)))
    };
  }
  function positionContextHint(root,toast=document.getElementById('cti-context-hint')) {
    if(!toast?.isConnected)return;
    const mascot=root.dataset.docked==='true'?document.getElementById(MASCOT_ID):null;
    const edge=mascot?.dataset.visible==='true'?root.dataset.dockEdge:null;
    const anchor=(edge?mascot:root).getBoundingClientRect();
    const placed=contextHintGeometry(anchor,{width:toast.offsetWidth,height:toast.offsetHeight},{width:innerWidth,height:innerHeight},edge);
    toast.style.left=`${placed.left}px`;toast.style.top=`${placed.top}px`;
  }
  function maybeContextHint(root, selected, health, id) {
    if(!id || !selected || localStorage.getItem('cti-context-reminders')==='false')return;
    const used=selected.latest_context_percent;
    const level=health?.recommendHandoff?'compression':used>=85?'85':used>=75?'75':null;
    if(!level)return;
    let seen={};try{seen=JSON.parse(localStorage.getItem('cti-context-hints')||'{}')}catch{}
    const key=String(id)+':'+level;
    if(seen[key] || Date.now()-(seen[String(id)+':last']||0)<1800000)return;
    seen[key]=Date.now();seen[String(id)+':last']=Date.now();
    const recent=Object.fromEntries(Object.entries(seen).sort((a,b)=>b[1]-a[1]).slice(0,200));
    localStorage.setItem('cti-context-hints',JSON.stringify(recent));
    document.getElementById('cti-context-hint')?.remove();
    const toast=document.createElement('aside');toast.id='cti-context-hint';toast.setAttribute('role','status');
    toast.style.cssText='position:fixed;z-index:2147483647;max-width:280px;padding:12px 16px;border-radius:12px;background:Canvas;color:CanvasText;border:1px solid #8885;box-shadow:0 6px 24px #0002;font:12px/1.6 system-ui;-webkit-app-region:no-drag';
    const zh=uiLanguage()==='zh';
    toast.textContent=level==='compression'?(zh?'压缩负担较高，可在当前步骤完成后整理交接，换新对话继续。':'Compression overhead is high. Consider a handoff after this step.'):(zh?`上下文已用 ${Math.round(used)}%。可在阶段完成后整理交接；这不是费用上限。`:`Context ${Math.round(used)}% used. Consider a handoff at a task boundary; this is not a pricing limit.`);
    document.body.appendChild(toast);
    positionContextHint(root,toast);
    const timer=setTimeout(()=>toast.remove(),7000);root.__ctiClearHint=()=>{clearTimeout(timer);toast.remove();};
  }
  function updateHudTitle(root) {
    const title = root.querySelector('[data-cti-title]');
    if (!title) return;
    const collapsed = root.getAttribute('data-collapsed') === 'true';
    const total = root.__ctiSessionTotalTokens;
    const q = window.__codexContextTokenInspectorPayload?.quota;
    const live = q?.status === 'live' && Date.now()/1000-q.updatedAt < 120;
    const windows = live ? q.windows || [] : [];
    const remaining = windows.length ? Math.min(...windows.map(w => w.remaining)) : null;
    root.setAttribute('data-tone', quotaTone(remaining));
    title.setAttribute('aria-expanded', String(!collapsed));
    const compact = windows.map(w => `${windowLabel(w,true)} ${Math.round(w.remaining)}%`).join(' · ');
    const text = collapsed ? (compact || `${tr('monitor')} · —`) : tr('monitor');
    title.title = toneLabel(quotaTone(remaining));
    if (collapsed) {
      const cell=(label,value,tone,fill,sub='',figure=null)=>`<span class="cti-mini" data-tone="${tone}"><span class="cti-battery" aria-hidden="true"><i style="height:${fill||0}%"></i></span><span class="cti-mini-copy"><small>${label}</small><strong>${figure!=null?figure:(value==null?'—':Math.round(value)+'%')}</strong>${sub?`<em>${sub}</em>`:''}</span></span>`;
      const ctx=root.__ctiContext;
      const h=root.__ctiHealth;
      const sub=h?.count ? `↻${h.count} · ${h.after==null?'…':token(h.after)}` : '';
      const zhComp=uiLanguage()==='zh';
      const stopped=live&&(q.ordinaryUsageAllowed===false||!!q.rateLimitReachedType);
      // The figure beside the meter is how long that window can still carry the
      // work, not its share: the meter already draws the share, and only a
      // duration answers whether what is ahead of you fits. A block overrides
      // both, because a stopped account has an availability question, not a
      // magnitude one - and the collapsed bar is where that has to be readable
      // without a hover.
      const html=windows.map(w=>cell(windowLabel(w,true),w.remaining,stopped?'low':quotaTone(w.remaining),w.remaining,
        '',stopped?(zhComp?'已停':'stopped'):windowBudgetText(w))).join('')
        +cell(zhComp?'CTX 已用':'CTX used',ctx,contextTone(ctx),ctx,sub);
      if(title.innerHTML!==html)title.innerHTML=html;
      // The visible text trades percentages for durations, so the accessible
      // name keeps both. It starts from the compact reading rather than from
      // the title's own text, which in this branch already is that reading.
      const budget=stopped?(zhComp?'账户已达上限':'Account at its limit'):accountBudgetText(q);
      title.setAttribute('aria-label',[compact,budget,`${zhComp?'上下文已用':'Context used'} ${pct(ctx)}`].filter(Boolean).join(' · '));
    } else if (title.textContent !== text) title.textContent = text;
    updateHudLanguage(root);
  }
  function clearFooters() {
    document.querySelectorAll(`[${FOOTER_ATTR}]`).forEach(node => node.remove());
    document.querySelectorAll(`[${CHIP_ATTR}]`).forEach(node => node.remove());
  }
  function detailForCurrentThread(payload) {
    const details = payload.detailsByThread || {};
    for (const key of threadKeys(activeThreadId() || payload.activeThreadId)) {
      if (details[key]) return details[key];
    }
    return null;
  }
  function scheduleDetailApply(payload) {
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
      if (window.__codexContextTokenInspectorApplying) return;
      window.__codexContextTokenInspectorApplying = true;
      try {
        const currentDetail = detailForCurrentThread(payload) || detailForVisiblePage(payload);
        payload.currentDetailThreadId = currentDetail?.thread_id || null;
        applyHud(payload, currentDetail);
        if (currentDetail) {
          applyFooters(currentDetail);
        } else {
          clearFooters();
        }
      } finally {
        setTimeout(() => { window.__codexContextTokenInspectorApplying = false; }, 0);
      }
    };
      if (window.requestIdleCallback) {
        window.__codexContextTokenInspectorIdleCallback = window.requestIdleCallback(work, { timeout: 900 });
      } else {
        setTimeout(work, 0);
      }
    };
    window.__codexContextTokenInspectorDetailTimer = setTimeout(run, 220);
  }
  function applyAll(payload) {
    window.__codexContextTokenInspectorApplying = true;
    try {
      payload.activeThreadId = activeThreadId() || payload.activeThreadId;
      applySidebar(payload.summaries || []);
      // The active sidebar row is the authoritative session identity. Visible
      // text matching remains a fallback for app builds that omit that marker.
      const currentDetail = detailForCurrentThread(payload) || detailForVisiblePage(payload);
      payload.currentDetailThreadId = currentDetail?.thread_id || null;
      applyHud(payload, currentDetail);
    } finally {
      setTimeout(() => { window.__codexContextTokenInspectorApplying = false; }, 0);
    }
    scheduleDetailApply(payload);
  }
  function installObserver(payload) {
    window.__codexContextTokenInspectorPayload = payload;
    if (window.__codexContextTokenInspectorObserver) return;
    let timer = null;
    const observer = new MutationObserver(records => {
      if (window.__codexContextTokenInspectorApplying) return;
      const activeChanged = records.some(record =>
        record.type === 'attributes' &&
        (record.attributeName === 'data-app-action-sidebar-thread-active' || record.attributeName === 'aria-current')
      );
      // Session switches deserve a fast path. Ordinary render churn is batched
      // to avoid repeatedly walking the message tree while a response streams.
      if (timer && !activeChanged) return;
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        timer = null;
        applyAll(window.__codexContextTokenInspectorPayload);
      }, activeChanged ? 80 : 300);
    });
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['data-app-action-sidebar-thread-active', 'aria-current'],
    });
    window.__codexContextTokenInspectorObserver = observer;
  }

  function resetStaleRuntime() {
    if (!runtimeChanged) return;
    window.__codexContextTokenInspectorObserver?.disconnect();
    window.__codexContextTokenInspectorObserver = null;
    hideSidebarTooltip();
    if (window.__codexContextTokenInspectorDetailTimer) {
      clearTimeout(window.__codexContextTokenInspectorDetailTimer);
      window.__codexContextTokenInspectorDetailTimer = null;
    }
    if (window.__codexContextTokenInspectorIdleCallback && window.cancelIdleCallback) {
      window.cancelIdleCallback(window.__codexContextTokenInspectorIdleCallback);
      window.__codexContextTokenInspectorIdleCallback = null;
    }
    // Position, collapse state, and unit remain in localStorage and are restored
    // when the versioned HUD is recreated.
    document.getElementById(ROOT_ID)?.__ctiRemoveResize?.();
    document.getElementById(ROOT_ID)?.__ctiClearHint?.();
    document.getElementById(ROOT_ID)?.remove();
    document.getElementById(MASCOT_ID)?.remove();
  }

  resetStaleRuntime();
  ensureDefaultUnit();
  ensureStyle();
  installSidebarHoverDelegation();
  installObserver(payload);
  applyAll(payload);
  // Leave a data-only entry point behind. The resident injector pushes a fresh
  // reading every ten seconds, and once this runtime is applied it can do so
  // through this handle instead of re-parsing the whole script (which carries
  // the companion bitmaps) each time. The observer holds the payload; applyAll
  // re-renders from the one passed here.
  window.__codexContextTokenInspectorUpdate = nextPayload => {
    installObserver(nextPayload);
    applyAll(nextPayload);
  };
  return {
    ok: true,
    summaries: (payload.summaries || []).length,
    activeThreadId: activeThreadId() || payload.activeThreadId,
    selectedThreadId: payload.selectedThreadId,
    currentDetailThreadId: payload.currentDetailThreadId || null,
    assistantNodes: assistantNodes().length,
    replyChips: document.querySelectorAll(`[${CHIP_ATTR}]`).length,
    dom: payload.dom,
  };
})
"""

# Companion artwork is inlined as data URIs. The plugin install copies only the
# scripts directory, so referencing files under assets/ would break every
# installed copy, and the overlay renders in the Codex window, where a file://
# image would be blocked anyway.
INJECTION_SCRIPT = INJECTION_SCRIPT.replace(
    "__COMPANION_ART__",
    json.dumps(COMPANION_ART, ensure_ascii=False, separators=(",", ":")),
)

# Read back from the script rather than restated here, so the number the panel
# reports is by construction the one this process actually pushes.
_RUNTIME_VERSION = re.search(r"const RUNTIME_VERSION = (\d+);", INJECTION_SCRIPT)
if _RUNTIME_VERSION is None:
    raise RuntimeError("RUNTIME_VERSION is missing from the injected script")
RUNTIME_VERSION = int(_RUNTIME_VERSION.group(1))


def build_stamp() -> dict:
    """What this process runs, next to what was last installed on disk.

    The runtime version travels with this process; the plugin version and the
    cachebuster are read from the record the installer writes. When a reinstall
    has landed but this process has not restarted they disagree, and that
    disagreement is the answer to "why has nothing changed".
    """
    try:
        recorded = json.loads((runtime_root() / "build_info.json").read_text(encoding="utf-8"))
        recorded = recorded if isinstance(recorded, dict) else {}
    except (OSError, ValueError):
        recorded = {}
    return {"runtimeVersion": RUNTIME_VERSION,
            "pluginVersion": recorded.get("pluginVersion"),
            "cachebuster": recorded.get("cachebuster"),
            "installedAt": recorded.get("installedAt")}


BUILD_STAMP = build_stamp()


def push(client: CDPClient, payload: dict[str, Any]) -> Any:
    """Deliver a payload, re-parsing the script only when the renderer is stale.

    The injected script is large because it carries the companion bitmaps. A
    renderer already running this runtime has left a data-only entry point
    behind, so a fresh reading can go through it instead of re-sending and
    re-parsing the whole script every ten seconds. The probe falls back to a
    full injection when the renderer was replaced (the version handle is gone)
    or when the entry point did not survive.
    """
    serialized = json.dumps(payload, ensure_ascii=False)
    applied = client.evaluate(
        f"window.__codexContextTokenInspectorRuntimeVersion === {RUNTIME_VERSION}"
        f" && typeof window.__codexContextTokenInspectorUpdate === 'function'"
    )
    if applied:
        return client.evaluate(f"window.__codexContextTokenInspectorUpdate({serialized})")
    return client.evaluate(f"({INJECTION_SCRIPT})({serialized})")


def inject_once(client: CDPClient, roots: list[str], limit: int, detail_limit: int) -> Any:
    state = runtime_state(client)
    payload = build_payload(roots, limit, state.get("activeThreadId"), detail_limit=detail_limit)
    payload['quota'] = QUOTA_READER.snapshot(force=state.get('refresh', False))
    payload['build'] = BUILD_STAMP
    payload['update'] = UPDATE_CHECKER.snapshot()
    payload['dom'] = state.get('dom')
    active = normalize_thread_id(state.get('activeThreadId') or payload.get('selectedThreadId') or '')
    selected = next((s for s in payload['summaries'] if normalize_thread_id(s.get('thread_id') or '') == active), None)
    if selected is None and payload['summaries']:
        selected = payload['summaries'][0]
        active = normalize_thread_id(selected.get('thread_id') or '')
    path = session_file_for_thread(roots, active) if active else None
    payload['health'] = context_health.scan(path) if path else None
    context = {key:selected.get(key) for key in ('latest_context_percent','latest_context_tokens','context_window','latest_turn_input_tokens','latest_turn_cached_input_tokens','model','reasoning_effort')} if selected else None
    try:
        HISTORY.update(payload['quota'], context, payload['health'], recent_breakdown(payload['summaries']))
    except OSError:
        pass
    QUOTA_ALERTS.check(payload['quota'], enabled=state.get('alerts', False), language=state.get('language', 'zh'))
    return push(client, payload)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Codex DevTools port.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum recent sessions to inspect.")
    parser.add_argument(
        "--detail-limit",
        type=int,
        default=DETAIL_SESSION_LIMIT,
        help="Compatibility switch; zero disables details, otherwise only the active task is parsed.",
    )
    parser.add_argument("--interval", type=float, default=10.0, help="Refresh interval in seconds.")
    parser.add_argument("--once", action="store_true", help="Inject once and exit.")
    parser.add_argument("--quiet", action="store_true", help="Suppress successful refresh output.")
    parser.add_argument(
        "paths",
        nargs="*",
        help="Session JSONL files or directories. Defaults to ~/.codex/sessions and archived_sessions.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    roots = args.paths or [str(path) for path in inspector.DEFAULT_ROOTS]
    client: CDPClient | None = None
    last_error: str | None = None
    try:
        while True:
            try:
                if client is None:
                    target = select_target(devtools_targets(args.port))
                    client = CDPClient(str(target["webSocketDebuggerUrl"]))
                result = inject_once(client, roots, args.limit, args.detail_limit)
                try:
                    write_status("ok")
                except OSError:
                    pass
                if not args.quiet:
                    print(json.dumps(result, ensure_ascii=False), flush=True)
                last_error = None
            except (CDPError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
                try:
                    write_status("error", type(exc).__name__)
                except OSError:
                    pass
                if client is not None:
                    client.close()
                    client = None
                if args.once:
                    raise

                # A renderer can be replaced while the app remains open. Reconnect
                # in-process in that case; return to the launcher if CDP disappeared.
                try:
                    devtools_targets(args.port)
                except CDPError:
                    return 1
                message = f"Codex Monitor reconnecting after CDP error: {exc}"
                if message != last_error:
                    print(message, file=sys.stderr, flush=True)
                    last_error = message
                time.sleep(min(max(args.interval, 0.2), 2.0))
                continue
            if args.once:
                break
            time.sleep(args.interval)
    finally:
        if client is not None:
            client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
