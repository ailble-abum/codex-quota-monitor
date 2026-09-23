"""Project local session data into the compact overlay payload."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Iterable

import context_token_inspector as inspector


ASSISTANT_DETAIL_ITEM_LIMIT = 40
DETAIL_SESSION_LIMIT = 1
DETAIL_CACHE_LIMIT = 24
_DETAIL_CACHE: dict[str, tuple[int, int, dict[str, Any]]] = {}


def normalize_thread_id(value: Any) -> str:
    text = str(value or "")
    return text[6:] if text.startswith("local:") else text


def thread_keys(value: Any) -> list[str]:
    normalized = normalize_thread_id(value)
    return [normalized, f"local:{normalized}"] if normalized else []


def _compact(summary: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "thread_id", "cwd", "model", "reasoning_effort", "updated_at",
        "latest_context_tokens", "context_window", "latest_context_percent",
        "latest_turn_total_tokens", "latest_turn_input_tokens",
        "latest_turn_cached_input_tokens", "latest_turn_output_tokens",
        "latest_turn_reasoning_tokens", "session_total_tokens", "session_input_tokens",
        "session_cached_input_tokens", "session_output_tokens", "session_reasoning_tokens",
    )
    result = {key: summary.get(key) for key in fields}
    result.update({
        "thread_keys": thread_keys(summary.get("thread_id")),
        "hover": inspector.format_hover(summary),
        "footer": inspector.format_reply_footer(summary),
        "badge": compact_badge(summary),
    })
    return result


def _summaries(paths: Iterable[str], limit: int | None) -> list[dict[str, Any]]:
    files = inspector.session_files(paths, limit=limit)
    return [
        summary for summary in (inspector.summarize_session_fast(path) for path in files)
        if summary.get("session_total_tokens")
    ]


def _by_thread(summaries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for summary in summaries:
        for key in thread_keys(summary.get("thread_id")):
            result[normalize_thread_id(key)] = summary
            result[key] = summary
    return result


def build_payload(paths, limit, selected_thread_id, detail_limit=DETAIL_SESSION_LIMIT):
    summaries = _summaries(paths, limit)
    lookup = _by_thread(summaries)
    selected = lookup.get(normalize_thread_id(selected_thread_id)) if selected_thread_id else None
    if selected is None and selected_thread_id:
        active_path = session_file_for_thread(paths, selected_thread_id)
        if active_path is not None and str(active_path) not in {item.get("path") for item in summaries}:
            candidate = inspector.summarize_session_fast(active_path)
            if (normalize_thread_id(candidate.get("thread_id")) == normalize_thread_id(selected_thread_id)
                    and candidate.get("session_total_tokens")):
                summaries.append(candidate)
                selected = candidate
    selected = selected or (summaries[0] if summaries else None)

    detail = None
    details_by_thread: dict[str, dict[str, Any]] = {}
    if selected is not None and detail_limit and detail_limit > 0 and selected.get("path"):
        detail = _detail_payload(selected)
        for key in thread_keys(selected.get("thread_id")):
            details_by_thread[key] = detail

    return {
        "activeThreadId": selected_thread_id,
        "selectedThreadId": (selected or {}).get("thread_id") or selected_thread_id,
        "summaries": [_compact(summary) for summary in summaries],
        "detail": detail,
        "detailsByThread": details_by_thread,
        "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _detail_payload(summary: dict[str, Any]) -> dict[str, Any]:
    parsed = cached_session_detail(str(summary["path"]), summary)
    messages = [
        message for message in parsed.get("messages", [])
        if message.get("role") == "assistant" and message.get("token_usage")
    ]
    total = len(messages)
    visible = messages[-ASSISTANT_DETAIL_ITEM_LIMIT:]
    start = total - len(visible)
    items = []
    for position, message in enumerate(visible, start=1):
        assistant_index = start + position
        usage = message["token_usage"]
        items.append({
            "footer": message.get("token_footer"),
            "chip": inspector.format_reply_chip(
                usage,
                user_turn_index=message.get("turn_index"),
                user_total_turns=message.get("total_turns"),
                assistant_turn_index=assistant_index,
                assistant_total_turns=total,
            ),
            "tokenUsage": usage,
            "textPrefix": text_prefix(message.get("text")),
            "roundIndex": message.get("turn_index") or position,
            "totalRounds": message.get("total_turns") or total,
            "userTurnIndex": message.get("turn_index"),
            "userTotalTurns": message.get("total_turns"),
            "assistantTurnIndex": assistant_index,
            "assistantTotalTurns": total,
        })
    return {
        "thread_id": summary.get("thread_id"),
        "updated_at": summary.get("updated_at"),
        "footer": inspector.format_reply_footer(summary),
        "assistantFooters": [item["footer"] for item in items if item.get("footer")],
        "assistantChips": [item["chip"] for item in items],
        "assistantItems": items,
    }


def cached_session_detail(path: str, summary: dict[str, Any]) -> dict[str, Any]:
    try:
        stat = Path(path).stat()
        signature = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        return inspector.parse_session_detail(path, summary=summary)

    cached = _DETAIL_CACHE.get(path)
    if cached is not None:
        previous_mtime, previous_size, parsed = cached
        if signature == (previous_mtime, previous_size):
            return parsed
        if signature[1] > previous_size:
            rows, next_offset = inspector.read_jsonl_from_offset(path, previous_size)
            inspector.extend_session_detail(parsed, rows, summary=summary)
            _DETAIL_CACHE[path] = (signature[0], next_offset, parsed)
            return parsed

    parsed = inspector.parse_session_detail(path, summary=summary)
    if path not in _DETAIL_CACHE and len(_DETAIL_CACHE) >= DETAIL_CACHE_LIMIT:
        _DETAIL_CACHE.pop(next(iter(_DETAIL_CACHE)))
    _DETAIL_CACHE[path] = (signature[0], signature[1], parsed)
    return parsed


def compact_badge(summary: dict[str, Any]) -> str:
    percent = summary.get("latest_context_percent")
    if isinstance(percent, float):
        return f"{percent:.1f}% ctx"
    total = summary.get("session_total_tokens")
    return f"{total // 1000}k tok" if isinstance(total, int) else "tokens"


def text_prefix(value: Any, limit: int = 120) -> str:
    return " ".join(value.split())[:limit] if isinstance(value, str) else ""


def session_file_for_thread(paths: Iterable[str], thread_id: Any) -> Path | None:
    normalized = normalize_thread_id(thread_id)
    if not normalized:
        return None
    return next((path for path in inspector.session_files(paths, limit=None)
                 if normalized in path.stem), None)
