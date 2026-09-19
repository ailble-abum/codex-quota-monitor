"""Build the compact renderer payload and the active task's message details."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import context_token_inspector as inspector

ASSISTANT_DETAIL_ITEM_LIMIT = 40
DETAIL_SESSION_LIMIT = 1
DETAIL_CACHE_LIMIT = 24
_DETAIL_CACHE: dict[str, tuple[int, int, dict[str, Any]]] = {}


def build_payload(paths, limit, selected_thread_id, detail_limit=DETAIL_SESSION_LIMIT):
    files = inspector.session_files(paths, limit=limit)
    summaries = [inspector.summarize_session_fast(path) for path in files]
    summaries = [summary for summary in summaries if summary.get("session_total_tokens")]
    by_thread = {}
    for summary in summaries:
        thread_id = summary.get("thread_id")
        if not thread_id:
            continue
        normalized = normalize_thread_id(str(thread_id))
        by_thread[normalized] = summary
        by_thread[f"local:{normalized}"] = summary
    selected = summaries[0] if summaries else None
    active_selected = by_thread.get(normalize_thread_id(selected_thread_id or "")) if selected_thread_id else None
    if selected_thread_id and active_selected is None:
        active_path = session_file_for_thread(paths, selected_thread_id)
        known_paths = {str(summary.get("path")) for summary in summaries}
        if active_path and str(active_path) not in known_paths:
            summary = inspector.summarize_session_fast(active_path)
            normalized = normalize_thread_id(str(summary.get("thread_id") or ""))
            if normalized == normalize_thread_id(selected_thread_id) and summary.get("session_total_tokens"):
                summaries.append(summary)
                by_thread[normalized] = summary
                by_thread[f"local:{normalized}"] = summary
                active_selected = summary
    selected = active_selected or selected

    compact_summaries = [{
        "thread_id": summary.get("thread_id"),
        "thread_keys": thread_keys(summary.get("thread_id")),
        "cwd": summary.get("cwd"),
        "model": summary.get("model"),
        "reasoning_effort": summary.get("reasoning_effort"),
        "updated_at": summary.get("updated_at"),
        "latest_context_tokens": summary.get("latest_context_tokens"),
        "context_window": summary.get("context_window"),
        "latest_context_percent": summary.get("latest_context_percent"),
        "latest_turn_total_tokens": summary.get("latest_turn_total_tokens"),
        "latest_turn_input_tokens": summary.get("latest_turn_input_tokens"),
        "latest_turn_cached_input_tokens": summary.get("latest_turn_cached_input_tokens"),
        "latest_turn_output_tokens": summary.get("latest_turn_output_tokens"),
        "latest_turn_reasoning_tokens": summary.get("latest_turn_reasoning_tokens"),
        "session_total_tokens": summary.get("session_total_tokens"),
        "session_input_tokens": summary.get("session_input_tokens"),
        "session_cached_input_tokens": summary.get("session_cached_input_tokens"),
        "session_output_tokens": summary.get("session_output_tokens"),
        "session_reasoning_tokens": summary.get("session_reasoning_tokens"),
        "hover": inspector.format_hover(summary),
        "footer": inspector.format_reply_footer(summary),
        "badge": compact_badge(summary),
    } for summary in summaries]

    details_by_thread = {}
    detail = None
    # The active task is the demand signal. Sidebar rows need compact summaries,
    # but unrelated message histories do not belong in every ten-second push.
    for summary in [selected] if selected and detail_limit > 0 else []:
        if not summary.get("path"):
            continue
        parsed = cached_session_detail(str(summary["path"]), summary)
        messages = [message for message in parsed.get("messages", [])
                    if message.get("role") == "assistant" and message.get("token_usage")]
        total_rounds = len(messages)
        messages = messages[-ASSISTANT_DETAIL_ITEM_LIMIT:]
        start_index = total_rounds - len(messages)
        items = [{
            "footer": message.get("token_footer"),
            "chip": inspector.format_reply_chip(
                message["token_usage"], user_turn_index=message.get("turn_index"),
                user_total_turns=message.get("total_turns"),
                assistant_turn_index=start_index + index, assistant_total_turns=total_rounds),
            "tokenUsage": message["token_usage"],
            "textPrefix": text_prefix(message.get("text")),
            "roundIndex": message.get("turn_index") or index,
            "totalRounds": message.get("total_turns") or total_rounds,
            "userTurnIndex": message.get("turn_index"),
            "userTotalTurns": message.get("total_turns"),
            "assistantTurnIndex": start_index + index,
            "assistantTotalTurns": total_rounds,
        } for index, message in enumerate(messages, start=1)]
        item_detail = {
            "thread_id": summary.get("thread_id"),
            "updated_at": summary.get("updated_at"),
            "footer": inspector.format_reply_footer(summary),
            "assistantFooters": [item["footer"] for item in items if item.get("footer")],
            "assistantChips": [item["chip"] for item in items],
            "assistantItems": items,
        }
        for key in thread_keys(summary.get("thread_id")):
            details_by_thread[key] = item_detail
        detail = item_detail

    return {"activeThreadId": selected_thread_id,
            "selectedThreadId": (selected or {}).get("thread_id") or selected_thread_id,
            "summaries": compact_summaries, "detail": detail,
            "detailsByThread": details_by_thread,
            "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S")}


def cached_session_detail(path, summary):
    try:
        stat = Path(path).stat()
        signature = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        return inspector.parse_session_detail(path, summary=summary)
    cached = _DETAIL_CACHE.get(path)
    if cached:
        cached_mtime, cached_offset, parsed = cached
        if cached_mtime == signature[0] and cached_offset == signature[1]:
            return parsed
        if signature[1] > cached_offset:
            rows, next_offset = inspector.read_jsonl_from_offset(path, cached_offset)
            inspector.extend_session_detail(parsed, rows, summary=summary)
            _DETAIL_CACHE[path] = (signature[0], next_offset, parsed)
            return parsed
    parsed = inspector.parse_session_detail(path, summary=summary)
    if path not in _DETAIL_CACHE and len(_DETAIL_CACHE) >= DETAIL_CACHE_LIMIT:
        _DETAIL_CACHE.pop(next(iter(_DETAIL_CACHE)))
    _DETAIL_CACHE[path] = (signature[0], signature[1], parsed)
    return parsed


def compact_badge(summary):
    percent = summary.get("latest_context_percent")
    if isinstance(percent, float):
        return f"{percent:.1f}% ctx"
    total = summary.get("session_total_tokens")
    return f"{total // 1000}k tok" if isinstance(total, int) else "tokens"


def text_prefix(value, limit=120):
    return " ".join(value.split())[:limit] if isinstance(value, str) else ""


def normalize_thread_id(thread_id):
    return thread_id.removeprefix("local:") if thread_id.startswith("local:") else thread_id


def thread_keys(thread_id):
    if not thread_id:
        return []
    normalized = normalize_thread_id(str(thread_id))
    return [normalized, f"local:{normalized}"]


def session_file_for_thread(paths, thread_id):
    normalized = normalize_thread_id(thread_id or "")
    if not normalized:
        return None
    return next((path for path in inspector.session_files(paths, limit=None) if normalized in path.stem), None)
