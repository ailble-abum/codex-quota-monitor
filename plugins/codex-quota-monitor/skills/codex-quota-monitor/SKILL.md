---
name: codex-quota-monitor
description: Start and troubleshoot the local read-only Codex token and quota overlay.
---

# Codex Quota Monitor

Creator: Ailble. On Windows use the Windows adapter through `python scripts/monitorctl.py`; it does not use Swift or launchctl. Do not claim Windows task-scheduler/tray behavior is validated on macOS. Read the included Windows adapter help before first Windows installation.

The whole panel is a drag handle, not just its title row: any pointerdown that does not land on a control (button, input, select, textarea, summary, link, label) or on the scrollbar gutter starts a move. `[data-cti-title]` stays grabbable even though it is a button. The four corners are invisible resize targets; hovering a corner changes the pointer and dragging resizes from that corner. The bottom-right target remains keyboard-focusable and supports arrow-key resizing. The title row is `position: sticky` because the panel scrolls as one container -- without it the quota readout and window controls leave the viewport. Compact/expanded layouts are stored separately; reserve the top safe area and apply `-webkit-app-region: no-drag`. Position reset must clear both the legacy position key and `cti-layout-v2`, otherwise the new geometry will restore old coordinates.

The overlay can softly dock when released close to the left or right wall. Only the side walls dock, because every companion is drawn as a figure peeking in from a vertical edge; a layout stored by an older build that used the top or bottom edge is migrated to a free-floating panel. A docked overlay leaves only its selected companion visible; hover to reveal it, leave to hide it, click the companion to pin it open, or drag the revealed header to detach it. A docked bitmap companion carries no card, border, or plate -- the character floats against the window edge with the grip pill beside it; only the vector fallback keeps the glass card, which it needs for contrast on a light canvas. Docking can be disabled and the companion changed in display settings, where the picker is a collapsible `<details>` whose summary names the live skin so a collapsed section still identifies it. Free-floating overlays remain the ordinary full panel.

All six companion skins ship WebP artwork inlined into the injected script as data URIs, because the installer copies only the scripts directory and the renderer cannot read the plugin's assets. Run `python3 scripts/build_companion_art.py` after adding or replacing a render in `assets/companions`; it needs pillow and numpy at build time only. A skin whose artwork is missing falls back to its bundled inline vector, so check `--list` before describing the set as fully illustrated.

Quota labels derive from actual window durations, not primary/secondary array positions. A missing 5h window must not be synthesized. Unknown/absent limits are neither zero remaining nor unlimited.

Every reported window is an AND gate, so the collapsed bar and the quota headline answer with a time budget rather than a share: how long the account can keep working at the pace it has been spending, taken from whichever window binds first. A window that would refill before it runs out cannot bind within that horizon, so it is reported as "at least" plus a floor -- never present a floor as a measurement. A budget needs a window duration and a reset stamp; without both there is no duration to report and the bar falls back to the percentage rather than inventing a countdown.

A reached limit is a state, not a magnitude. The gauge then stops filling per window and becomes one stopped bar with a mark drawn across it, and the nearest reset is named with it. Do not restore per-window fills under a block: one spent window beside a healthy one reads as partly usable while the account is already stopped, which is the misreading the AND gate invites.

The settings panel footer and `monitorctl.py status` both name the installed build: the declared plugin version, the cachebuster Codex keys its cache directory on, the injected runtime version, and the install time. A plugin cache does not refresh on its own, and the injected runtime version is read back out of the script the injector actually holds. When the overlay looks unchanged, read that line before reading the diff -- a runtime version below the one in the source means the long-lived injector has not restarted, not that the code is wrong.

At most once per day, the resident monitor fetches the public repository `plugin.json` and compares its cachebuster with the installed build. The right-side settings button forces a new check and briefly confirms when the installed build is already current. The request sends no local version, account data, or conversation content. Only a newer build is promoted; network and parse failures remain silent so offline use is unchanged.

Context hints last seven seconds, default at 75%/85% of the reported window, and can be disabled in settings. These are heuristic workflow reminders, not researched universal cost-optimal values. Different models, cached input, repeated prefix reuse, and compaction policy matter; never promise a fixed-token handoff saves money. Preserve settings and avoid repeated prompts for the same task/stage.

Use `python3 scripts/monitorctl.py status` before starting to avoid duplicate monitors. Paths below are relative to the plugin root (two levels above this skill directory). The overlay defaults to the bottom-left and can be dragged or collapsed.

For first install or after a plugin update, run `python3 scripts/monitorctl.py install`. This deploys scripts into the standard Application Support directory and registers the LaunchAgent. For an installed LaunchAgent, run `python3 scripts/monitorctl.py start`. It survives the current task and waits when the app is closed. Do not use temporary shell background jobs as the persistent installation. The bundled `scripts/start_codex_monitor.sh` remains the launcher, and requires local CDP access. Its first connection may reopen the app; explain this before running when CDP is unavailable.

`install` writes every file before it touches launchd, restarts an agent whose definition is unchanged instead of rebuilding it, and restores the previous definition if a rebuild is refused. A restricted or sandboxed session can still return `Bootstrap failed: 5: Input/output error`; the command then syncs the runtime directory, names the agent that did not load, and exits non-zero. That is an environment limit, not a plugin fault - report it and ask the user to re-run the same command from a normal terminal. Never claim an agent is registered when `doctor` reports it not running.

Run `python3 scripts/monitorctl.py doctor` to verify the service, display connection, and authenticated quota independently. Do not report successful launch as proof that the overlay or quota works.

The menu bar prefixes its title with a warning after an injector failure, and `doctor` reports the owner-only injector health marker. A successful injection clears the warning. Message-level details are parsed and sent only for the task the renderer currently marks active; task switches populate on the next monitor tick.

Use `python3 scripts/monitorctl.py stop` to unload the service and remove the overlay. Use `python3 scripts/monitorctl.py show` to show or expand it without changing its saved layout, and `python3 scripts/monitorctl.py reset-position` to restore the overlay to the bottom-left. The current helper diagnoses the default CDP port 9222; if the launcher selected another port, inspect its log and use the injector's explicit `--port` option.

The monitor reads local Codex session JSONL files for token and context data. It separately reads `account/rateLimits/read` through the installed local Codex app-server, every 60 seconds, without model calls. Account credentials are not passed to the renderer. Missing quota is unavailable, never zero. Cached percentages are hidden on read failure or after 120 seconds because current account identity cannot then be verified. Do not infer an account balance from local token counts.

Explain that latest-request tokens are not a full user turn; cached input is part of input, and cumulative session tokens differ from current context occupancy. Report quota reset times in the user's local timezone. Keep the default view compact, with detailed token statistics available on expansion.

When local `turn_context` records include them, show the latest model and reasoning effort as descriptive session metadata. Do not infer either value from token volume, context size, or account quota.

The history page starts with a local seven-day report card and may rank cumulative session Tokens for up to 100 recent local sessions by model and short project-folder name. Treat both as relative local diagnostics, not billing data; do not persist conversation bodies or full project paths for this feature.

The quota color thresholds are green above 50% remaining, blue above 20% through 50%, and red at or below 20%. Context uses separate occupancy thresholds: 70% and 85%. Gray means unavailable, not zero. The compact header shows both quota windows and uses the more constrained window's color. These are display guidance thresholds, not official provider limits.

The account worker also requests `account/usage/read`. Treat lifetime, peak-day, streak, and daily bucket values as official activity summaries when returned, not as billing totals or quota percentages. Missing fields remain unavailable. Pace compares actual used percentage with a linear spend through the reported window, and projected exhaustion is shown only when that average pace reaches 100% before reset. Describe both as estimates that can change with model, task complexity, caching, and idle time.

Display the count and nearest expiry of available rate-limit reset credits when reported, but never persist or render credit IDs and never consume a reset without the user's explicit confirmation. Safe error codes may explain missing CLI, timeout, app-server, or account availability; local Token reading remains independent.

The `…` settings menu provides number formatting, restore position, and low-quota notifications. Notifications are off by default and should only be enabled at the user's request or through their own toggle. Deduplication survives restarts using hashed account/window/reset keys in the runtime directory; no account credentials or conversation logs are saved there. Do not claim notifications were delivered merely because a mock test passed or macOS accepted the request.

Never upload session logs or modify Codex.app, authentication files, or conversation JSONL files.

The compact display includes separate vertical meters for quota windows and context occupancy. Its compression suffix shows observed `compacted` events and the first distinct request input size afterward; this includes system/tool input and is not summary-only size. Do not equate cumulative tokens with context growth or claim compression always starts at the displayed window maximum. A 40% post-compaction baseline or two intervals of five requests or fewer triggers a heuristic handoff suggestion. The copy button only copies a handoff instruction; the current assistant still needs to produce the task-specific summary.

The installer also builds the native Swift menu-bar companion and starts its LaunchAgent. Both services are covered by `start` and `stop`. The menu opens a local seven-day quota trend page with actual collected samples only. Verify `monitorctl.py doctor` reports both services plus history. History starts on installation, remains local, stores numeric metadata without conversation content, and pauses when the app is closed. Old readings must be labeled stale; do not fabricate historical data or use fixture samples as live data.
