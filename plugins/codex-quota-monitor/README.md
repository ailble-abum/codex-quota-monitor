# Codex Quota Monitor

Created by **Ailble** · 创作人：**Ailble**. See [INTRODUCTION.md](INTRODUCTION.md) for the Chinese and English feature introduction.

## Interaction upgrade

The whole panel is a grab surface: drag it from the title row, the quota readout, or any gap between rows. Only controls that own the pointer keep it -- buttons, the unit selector, the disclosure summaries, and the corner resize grip. A pointerdown on the scrollbar gutter still belongs to the scroll container, so scrolling never turns into a drag. The small bottom-right grip resizes the panel and its typography; when focused, arrow keys resize it in 12px steps. Compact and expanded positions/sizes are remembered separately. Temporary viewport clamping does not overwrite the saved anchor. A 64px top safe area avoids the app title bar, and the overlay is explicitly marked as a non-native-drag region. The title row is pinned to the top of the panel, so the quota readout and the window controls stay reachable while the detail list is scrolled.

Soft edge docking is enabled by default. Release the panel within 14px of the left or right wall to tuck it away behind a small companion; hovering reveals the unchanged panel toward the screen interior, leaving hides it after 500ms, and clicking the companion pins it open. Drag the revealed header to detach it. Only the side walls dock: every companion is drawn as a figure peeking in from a vertical edge, so a top or bottom dock would have to lay the character on its side. A layout saved by an earlier build that used those edges is migrated to a free-floating panel. A docked bitmap companion draws no card and no plate -- the character sits against the window edge with the account gauge beside it, and only the vector fallback still gets the glass card it needs for contrast on a light canvas. Display settings can disable docking and choose between the companions; the picker is a collapsible section whose summary names the live skin, so a collapsed picker still says which one is docked.

All six companions ship illustrated artwork. `scripts/build_companion_art.py` keys the backdrop out of the source renders in `assets/companions`, crops each one flush against its own cut edge at a shared height, and rewrites both `assets/companions/web/*.webp` and the generated `scripts/companion_art.py` that inlines them as data URIs. Inlining is required rather than convenient: the installer copies only the scripts directory, and the overlay renders in the Codex window where a `file://` image would be blocked. Any skin without artwork falls back to its bundled inline vector, so a newly added companion can be wired up before its render exists.

Two backdrop styles are keyed. Five renders arrived on a baked-in checkerboard, which is separated by colour neutrality. The mint cat is a studio render instead: a flat near-black backdrop only a few levels below the character, with a lit wall rim down the right edge that the cat's ear and paw are cropped by. Its key is a brightness ramp over that narrow window, with the body taken as the largest connected blob and its interior filled -- the shaded underside of the head sits barely above the backdrop and would otherwise fade out. The frame is clipped just left of the rim, and the figure is padded vertically because a head study would otherwise read about twice the size of the busts it sits beside.

Only quota windows actually supplied by the account source are shown. A secondary-only weekly window is not relabeled as 5h. Unknown durations keep generic primary/secondary labels; absent windows are not invented as 100% or called unlimited. The same labels are used in the menu bar and history.

The gauge beside a docked companion draws one cell per quota window the account reports, so the cell count itself states how many independent limits are in force: a plan reporting both an hourly and a weekly window gets two cells, an account reporting a single window gets one. Each cell fills with its own window's remaining share and takes the same tier colour as the panel, so a healthy short window cannot hide a nearly spent long one behind a single healthy-looking bar. Every window has to have headroom, so reaching one stops the account while the other may still read comfortably -- the read carries `ordinaryUsageAllowed` and `rateLimitReachedType` alongside the shares for exactly that reason, and a reached account is framed around every cell and named in the tooltip. Before the first reading the cells are drawn as empty dashed slots rather than full ones, so an unknown account never reads as a healthy one; the figures themselves live in the companion's hover title, because a 7x17px cell has no room for text and 1% of it is under a fifth of a pixel.

Settings now include Chinese/English/automatic language and context hints. Hints appear for seven seconds at 75%/85% of the reported model window, or on the existing compaction recommendation. They are advisory task-boundary reminders, not universal cost thresholds, and are limited to once per stage/thread with a 30-minute cooldown. Switching context can lose useful state and caching, so the monitor never opens a new conversation automatically.

Display settings now include Mini, Standard, and Large presets. The offline seven-day history page also records context occupancy and cached-input share when those local token fields are available, so a user can see pressure and reuse trends rather than infer them from one reading.

Official reference: [prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) explains that cost depends on reuse and model pricing, and recommends measuring actual cached/input counts. [Compaction](https://developers.openai.com/api/docs/guides/compaction) describes configurable thresholds, not a fixed universally optimal handoff point. The monitor uses the window reported in local token events instead of assuming every model has a 258K window. Cached-input share is shown in details.

Windows adapters are provided separately from the macOS LaunchAgent/AppKit layer. The common quota reader uses a queue-backed pipe reader compatible with Windows, and runtime files go to `%LOCALAPPDATA%/CodexQuotaMonitor`. Windows OS integration requires real-machine validation; macOS/browser regression tests do not substitute for it.

Local macOS overlay: remaining account quota and reset times first, current context second, expandable request/session statistics. No model calls, telemetry, session uploads, or direct authentication-file edits.

The settings footer names the installed build and checks the public repository `plugin.json` at most once per day. A newer cachebuster produces an update notice and link. The request sends no local version, account data, or conversation content; failures are silent and do not affect offline monitoring.

The expanded local statistics and menu-bar menu show the latest session model and reasoning effort when a `turn_context` record provides them. This helps explain usage differences without guessing from Token totals.

The offline history page also compares cumulative session Tokens for the most recent 100 local sessions by model and by project-folder name. It stores only the short project folder name in the numeric history snapshot, not conversation text or full project paths. These rankings are relative local diagnostics, not billing totals.

## Operation

Run `python3 scripts/monitorctl.py status`, `start`, `stop`, `doctor`, or `reset-position`.
Run `python3 scripts/monitorctl.py install` after updating the plugin to install its scripts in `~/Library/Application Support/CodexQuotaMonitor/scripts` and register the LaunchAgent. This standard runtime directory is independent of versioned caches and Documents access restrictions. It starts on login and waits while Codex is closed. The original launcher may reopen the app to enable loopback CDP on initial connection.

`install` writes every file before it touches launchd, so a load that is refused never leaves stale scripts behind. An agent whose definition is unchanged is restarted in place rather than torn down and rebuilt; one whose definition changed is rebuilt, and a refused rebuild restores the previous definition. If launchd rejects the load - a restricted or sandboxed session can return `Bootstrap failed: 5: Input/output error` - the command still syncs the runtime directory, names the agent that did not load, and exits non-zero. Re-run it from a normal terminal to register that agent.

Quota uses the local Codex app-server protocol, sampled every 60 seconds on a background worker. Token logs and the overlay refresh every 10 seconds. The refresh button requests an earlier sample on the next tick. Missing or stale account results are hidden; no account snapshots or credentials are persisted. Reset timestamps use the system's local timezone.

The same app-server session also reads `account/usage/read` when available. The expanded overlay and menu bar show official lifetime and latest daily Token activity, while the history page includes up to 30 returned daily buckets. These activity totals are descriptive account statistics, not a bill and not a conversion of quota percentage.

Each reported quota window includes a linear pace comparison based on elapsed window time. When observed consumption would reach 100% before reset at the same average pace, the monitor shows an estimated exhaustion time. This is a projection, not a provider guarantee; future task size, model choice, caching, and idle periods can change it quickly.

When the account reports earned rate-limit reset credits, the monitor shows the available count and nearest expiration. It never stores or displays individual credit identifiers, and it does not consume a credit. Account-read failures use short local diagnostic categories while local session Token statistics continue independently.

## Colors and controls

- Quota remaining: green above 50%, blue above 20% through 50%, red at or below 20%. Missing values are neutral gray.
- Context used: green below 70%, blue from 70% up to 85%, red at or above 85%. These are visual guidance thresholds, not provider rules.
- The compact header shows both quota windows and takes its color from the lower remaining percentage.
- The `…` menu contains automatic/raw/K/M formatting, restore position, and the notification toggle. Existing number-format preferences are preserved.
- Notifications are off by default. When enabled they notify at or below 20%, once per account/window/reset. Delivery requires macOS notifications to be allowed. Only hashed deduplication keys and reset timestamps are stored in the runtime's `alerts.json` (owner-only), not credentials or session contents.
- Theme colors follow the app's color scheme; motion respects the system's reduced-motion setting. Details remain open across refreshes and reopen on the next launch if left open.

The separate app-server reads the local CLI account. If desktop and CLI use different accounts, these limits refer to the CLI account; compare with the desktop account's built-in usage display after switching accounts. The monitor does not change accounts.

## Validation

`python3 scripts/test_quota_reader.py`

`python3 scripts/monitorctl.py doctor`

## Limitations

CDP and DOM integration can change with app updates. The helper currently checks port 9222; the underlying launcher can resolve alternate ports. Numbers reflect the latest available request record, not streaming token-by-token usage.

## Compact meters, compression, and history

The compact pill has independent 5-hour, weekly, and context-used vertical meters. Under context, `↻3 · 45K` means three observed compactions and a 45K first request following the latest compaction, not 45K of summary text alone.

Compression statistics use explicit `compacted` records. The first subsequent distinct token-usage record provides an approximate post-compaction request size, including system/tool input. No size is invented before that request arrives. Recommendations appear when that value is at least 40% of the context window, or when the last two observed compaction intervals are each five distinct requests or fewer. These are configurable-in-code heuristics, not official thresholds or proof of information loss. Compression does not necessarily wait for a full context window and its output need not grow monotonically.

The handoff button copies a request for the current assistant to prepare an evidence-based handoff. It does not claim to have summarized the task, create a new conversation, or send anything automatically.

Installation compiles an AppKit menu-bar companion with the installed Swift compiler, then registers `local.codex-quota-menu`. It reads the same local snapshot; it does not duplicate quota requests. Its menu shows quotas, context, compression, and opens an offline seven-day trend page. Use `monitorctl.py show` to show or expand the overlay while preserving its layout; use `reset-position` only when you want the default position. `stop` stops both services; `start` starts both.

Numeric snapshots and a rolling seven-day quota history are stored owner-only under Application Support. History is limited to 10,080 samples, filtered to the currently sampled account, and starts from enabling this version. Reset boundaries and gaps are not joined on the chart. There are no conversation bodies or credentials in these files. Quit Codex to pause collection; the menu marks old quota data unavailable after 120 seconds. Delete only `history.json`, `history.html`, and `snapshot.json` in the plugin runtime directory if you want to clear history while both services are stopped.

## Rollback

Stop the service before reverting source changes. The preceding installed 0.1.0 cache was preserved during this update. Restoring the previous LaunchAgent script path and reloading that service restores its earlier runtime; keep the current source separately if rolling back. No conversation or authentication files are modified by this plugin.
