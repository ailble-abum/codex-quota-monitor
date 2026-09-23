#!/usr/bin/env python3
"""Read-only parser for the token snapshots kept in local Codex sessions.

The reader deliberately has no renderer or transport dependency. It exposes a
small data contract to ``payload_builder``: summaries are bounded dictionaries,
and details are an append-only list of user/assistant messages.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
from pathlib import Path
from typing import Any, Iterable, Iterator


_CODEX_HOME = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
DEFAULT_ROOTS = [_CODEX_HOME / "sessions", _CODEX_HOME / "archived_sessions"]
THREAD_ID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_READ_CHUNK = 256 * 1024


def _row(raw: bytes | str) -> dict[str, Any] | None:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def comma(value: int | None) -> str:
    return "-" if value is None else f"{value:,}"


def pct(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round(numerator * 100 / denominator, 1)


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Yield valid object rows and ignore a malformed line without stopping."""
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = _row(line)
                if value is not None:
                    yield value


def read_jsonl_reverse(path: Path, chunk_size: int = _READ_CHUNK) -> Iterator[dict[str, Any]]:
    """Read complete JSONL records from newest to oldest."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    with Path(path).open("rb") as handle:
        end = handle.seek(0, os.SEEK_END)
        carry = b""
        while end:
            amount = min(chunk_size, end)
            end -= amount
            handle.seek(end)
            block = handle.read(amount) + carry
            parts = block.split(b"\n")
            carry = parts.pop(0)
            for line in reversed(parts):
                if line.strip():
                    value = _row(line)
                    if value is not None:
                        yield value
        if carry.strip():
            value = _row(carry)
            if value is not None:
                yield value


def token_count_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    event = row.get("payload")
    if row.get("type") != "event_msg" or not isinstance(event, dict):
        return None
    if event.get("type") != "token_count" or not isinstance(event.get("info"), dict):
        return None
    return event["info"]


def as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return int(value)
    return None


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def usage_summary_from_token_info(token_info: dict[str, Any]) -> dict[str, Any]:
    latest = _mapping(token_info.get("last_token_usage"))
    lifetime = _mapping(token_info.get("total_token_usage"))
    window = as_int(token_info.get("model_context_window"))
    context = as_int(latest.get("input_tokens"))
    return {
        "context_window": window,
        "latest_context_tokens": context,
        "latest_context_percent": pct(context, window),
        "latest_turn_total_tokens": as_int(latest.get("total_tokens")),
        "latest_turn_input_tokens": as_int(latest.get("input_tokens")),
        "latest_turn_cached_input_tokens": as_int(latest.get("cached_input_tokens")),
        "latest_turn_output_tokens": as_int(latest.get("output_tokens")),
        "latest_turn_reasoning_tokens": as_int(latest.get("reasoning_output_tokens")),
        "session_total_tokens": as_int(lifetime.get("total_tokens")),
        "session_input_tokens": as_int(lifetime.get("input_tokens")),
        "session_cached_input_tokens": as_int(lifetime.get("cached_input_tokens")),
        "session_output_tokens": as_int(lifetime.get("output_tokens")),
        "session_reasoning_tokens": as_int(lifetime.get("reasoning_output_tokens")),
    }


def infer_thread_id(path: Path) -> str:
    stem = Path(path).stem
    matches = THREAD_ID_PATTERN.findall(stem)
    if matches:
        return matches[-1]
    return stem.rsplit("-", 1)[-1] if "-" in stem else stem


def _summary(
    path: Path,
    meta: dict[str, Any],
    turn: dict[str, Any],
    token_info: dict[str, Any] | None,
    token_timestamp: str | None,
    newest_timestamp: str | None,
    token_events: int | None,
) -> dict[str, Any]:
    usage = usage_summary_from_token_info(token_info or {})
    return {
        "path": str(path),
        "thread_id": meta.get("id") or infer_thread_id(path),
        "cwd": meta.get("cwd"),
        "model_provider": meta.get("model_provider"),
        "model": turn.get("model"),
        "reasoning_effort": turn.get("effort"),
        "created_at": meta.get("timestamp"),
        "updated_at": token_timestamp or newest_timestamp,
        "token_events": token_events,
        **usage,
    }


def summarize_session(path: str | Path) -> dict[str, Any]:
    """Scan a session once, retaining the newest usable values."""
    source = Path(path).expanduser()
    meta: dict[str, Any] = {}
    turn: dict[str, Any] = {}
    token: dict[str, Any] | None = None
    token_time: str | None = None
    newest: str | None = None
    count = 0
    for row in read_jsonl(source):
        stamp = row.get("timestamp")
        if newest is None and isinstance(stamp, str):
            newest = stamp
        if row.get("type") == "session_meta" and isinstance(row.get("payload"), dict):
            meta = row["payload"]
        elif row.get("type") == "turn_context" and isinstance(row.get("payload"), dict):
            turn = row["payload"]
        info = token_count_payload(row)
        if info is not None:
            count += 1
            token = info
            token_time = stamp if isinstance(stamp, str) else None
    return _summary(source, meta, turn, token, token_time, newest, count)


def summarize_session_fast(path: str | Path) -> dict[str, Any]:
    """Read metadata from the head and current values from the tail."""
    source = Path(path).expanduser()
    meta: dict[str, Any] = {}
    for row in read_jsonl(source):
        if row.get("type") == "session_meta" and isinstance(row.get("payload"), dict):
            meta = row["payload"]
            break

    newest: str | None = None
    token: dict[str, Any] | None = None
    token_time: str | None = None
    turn: dict[str, Any] = {}
    for row in read_jsonl_reverse(source):
        stamp = row.get("timestamp")
        if newest is None and isinstance(stamp, str):
            newest = stamp
        if token is None:
            info = token_count_payload(row)
            if info is not None:
                token = info
                token_time = stamp if isinstance(stamp, str) else None
        if not turn and row.get("type") == "turn_context" and isinstance(row.get("payload"), dict):
            turn = row["payload"]
        if token is not None and turn:
            break
    return _summary(source, meta, turn, token, token_time, newest, None)


def message_text(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    pieces = [item.get("text", "") for item in content if isinstance(item, dict)
              and isinstance(item.get("text"), str)]
    return "\n\n".join(pieces).strip()


def should_skip_message(role: str, text: str) -> bool:
    if role != "user":
        return False
    text = text.strip()
    return text.startswith("<environment_context>") or text.startswith("<permissions instructions>")


def parse_session_detail(
    path: str | Path,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = Path(path).expanduser()
    result: dict[str, Any] = {
        "summary": summary if summary is not None else summarize_session(source),
        "meta": {},
        "messages": [],
        "_pending_assistant_index": None,
        "_current_turn_index": 0,
    }
    return extend_session_detail(result, read_jsonl(source), summary=summary)


def extend_session_detail(
    detail: dict[str, Any],
    rows: Iterable[dict[str, Any]],
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply new append-only rows to an already parsed detail object."""
    meta = detail.setdefault("meta", {})
    messages = detail.setdefault("messages", [])
    pending = detail.get("_pending_assistant_index")
    turn_number = detail.get("_current_turn_index", 0)
    if not isinstance(turn_number, int):
        turn_number = 0

    for row in rows:
        payload = row.get("payload")
        if row.get("type") == "session_meta" and isinstance(payload, dict):
            meta.clear()
            meta.update(payload)
            continue
        if row.get("type") == "response_item" and isinstance(payload, dict):
            if payload.get("type") != "message":
                continue
            role = payload.get("role")
            if role not in {"user", "assistant"}:
                continue
            text = message_text(payload)
            if should_skip_message(role, text):
                continue
            if role == "user":
                turn_number += 1
            messages.append({
                "timestamp": row.get("timestamp"),
                "role": role,
                "text": text,
                "token_footer": None,
                "token_usage": None,
                "turn_index": turn_number if role == "assistant" and turn_number else None,
                "total_turns": None,
            })
            if role == "assistant":
                pending = len(messages) - 1
            continue
        info = token_count_payload(row)
        if info is not None and pending is not None and 0 <= pending < len(messages):
            usage = usage_summary_from_token_info(info)
            messages[pending]["token_usage"] = usage
            messages[pending]["token_footer"] = format_reply_footer(usage)
            pending = None

    for message in messages:
        message["total_turns"] = turn_number or None
    if summary is not None:
        detail["summary"] = summary
    detail["_pending_assistant_index"] = pending
    detail["_current_turn_index"] = turn_number
    return detail


def read_jsonl_from_offset(path: str | Path, offset: int) -> tuple[list[dict[str, Any]], int]:
    source = Path(path).expanduser()
    if offset < 0:
        raise ValueError("offset must be non-negative")
    with source.open("rb") as handle:
        handle.seek(offset)
        data = handle.read()
    if not data:
        return [], offset
    newline = data.rfind(b"\n")
    if newline < 0:
        return [], offset
    complete = data[:newline + 1]
    rows = []
    for line in complete.splitlines():
        if line.strip():
            value = _row(line)
            if value is not None:
                rows.append(value)
    return rows, offset + len(complete)


def render_markdownish(text: str) -> str:
    return html.escape(text).replace("\n", "<br>")


def session_files(paths: Iterable[str], limit: int | None = None) -> list[Path]:
    found: set[Path] = set()
    for raw in paths:
        candidate = Path(os.path.expanduser(raw))
        if candidate.is_file() and candidate.suffix == ".jsonl":
            found.add(candidate)
        elif candidate.is_dir():
            found.update(path for path in candidate.rglob("*.jsonl") if path.is_file())
    ranked = []
    for path in found:
        try:
            stat = path.stat()
        except OSError:
            continue
        ranked.append((stat.st_mtime_ns, str(path), path))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    result = [item[2] for item in ranked]
    return result if limit is None else result[:max(0, limit)]


def format_reply_footer(summary: dict[str, Any]) -> str:
    percent = summary.get("latest_context_percent")
    shown_percent = f"{percent:.1f}%" if isinstance(percent, float) else "-"
    return (
        f"context: {comma(summary.get('latest_context_tokens'))} / "
        f"{comma(summary.get('context_window'))} ({shown_percent}) | "
        f"turn: {comma(summary.get('latest_turn_total_tokens'))} tokens "
        f"(in {comma(summary.get('latest_turn_input_tokens'))}, "
        f"out {comma(summary.get('latest_turn_output_tokens'))}, "
        f"reasoning {comma(summary.get('latest_turn_reasoning_tokens'))}) | "
        f"session: {comma(summary.get('session_total_tokens'))} tokens"
    )


def format_reply_chip(
    summary: dict[str, Any],
    round_index: int | None = None,
    total_rounds: int | None = None,
    user_turn_index: int | None = None,
    user_total_turns: int | None = None,
    assistant_turn_index: int | None = None,
    assistant_total_turns: int | None = None,
) -> str:
    percent = summary.get("latest_context_percent")
    shown_percent = f" ({percent:.1f}%)" if isinstance(percent, float) else ""
    chip = (
        f"Token: Current {comma(summary.get('latest_context_tokens'))}/"
        f"{comma(summary.get('context_window'))}{shown_percent} | "
        f"Total {comma(summary.get('latest_turn_total_tokens'))}/"
        f"{comma(summary.get('session_total_tokens'))}"
    )
    user_index = user_turn_index if user_turn_index is not None else round_index
    user_total = user_total_turns if user_total_turns is not None else total_rounds
    assistant_index = assistant_turn_index if assistant_turn_index is not None else round_index
    assistant_total = assistant_total_turns if assistant_total_turns is not None else total_rounds
    if user_index is not None and user_total is not None:
        chip += f"   Rounds：User {user_index}/{user_total}"
        if assistant_index is not None and assistant_total is not None:
            chip += f"  | Assistant {assistant_index}/{assistant_total}"
    elif assistant_index is not None and assistant_total is not None:
        chip += f"   Rounds：Assistant {assistant_index}/{assistant_total}"
    return chip


def format_hover(summary: dict[str, Any]) -> str:
    return "\n".join([
        f"Session total  {comma(summary.get('session_total_tokens'))}",
        f"Input          {comma(summary.get('session_input_tokens'))}",
        f"Cached input   {comma(summary.get('session_cached_input_tokens'))}",
        f"Output         {comma(summary.get('session_output_tokens'))}",
        f"Reasoning      {comma(summary.get('session_reasoning_tokens'))}",
    ])


def format_percent(value: Any) -> str:
    return f"{value:.1f}%" if isinstance(value, float) else "-"


def context_pressure(value: Any) -> str:
    if not isinstance(value, float):
        return "UNKNOWN"
    return "HIGH" if value >= 85 else "WATCH" if value >= 70 else "OK"


def print_table(summaries: list[dict[str, Any]]) -> None:
    headers = ["updated", "thread", "context", "turn", "session", "cwd"]
    rows = [[
        str(item.get("updated_at") or "-")[:19],
        str(item.get("thread_id") or "-")[:12],
        f"{comma(item.get('latest_context_tokens'))}/{comma(item.get('context_window'))}",
        comma(item.get("latest_turn_total_tokens")),
        comma(item.get("session_total_tokens")),
        str(item.get("cwd") or "-"),
    ] for item in summaries]
    widths = [max([len(header)] + [len(row[index]) for row in rows])
              for index, header in enumerate(headers)]
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Session JSONL files or directories.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum sessions to inspect.")
    parser.add_argument("--format", choices=["table", "json", "hover", "footer"], default="table")
    parser.add_argument("--latest", action="store_true", help="Only show the newest matching session.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    roots = args.paths or [str(path) for path in DEFAULT_ROOTS]
    amount = 1 if args.latest else args.limit
    summaries = [summarize_session(path) for path in session_files(roots, limit=amount)]
    summaries = [item for item in summaries if item.get("token_events")]
    if args.format == "json":
        print(json.dumps(summaries, ensure_ascii=False, indent=2))
    elif args.format == "hover":
        print("\n\n".join(format_hover(item) for item in summaries))
    elif args.format == "footer":
        print("\n".join(format_reply_footer(item) for item in summaries))
    else:
        print_table(summaries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
