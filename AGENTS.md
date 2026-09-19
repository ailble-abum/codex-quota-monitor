# Repository maintenance

For requested changes to this repository, update the source under `plugins/codex-quota-monitor`, run the Python tests and Swift typecheck, update the plugin cachebuster, reinstall the local plugin, and verify `monitorctl.py doctor` when the change affects runtime behavior.

The test suite must stay runnable on Python 3.9, which is what the overlay gets from the system interpreter on the systems this plugin supports. The GitHub runner default is newer, so it will not catch an evaluated 3.10-only annotation; the workflow pins 3.9 for this reason.

Reinstalling needs a normal terminal. A restricted or sandboxed session cannot register LaunchAgents - `launchctl bootstrap` returns `5: Input/output error` for any plist, not just this plugin's - and it may not permit `ps`, which the launcher's process detection needs. `install` now syncs the runtime directory before it touches launchd, so a refused load still updates the scripts; report the agent that failed and hand the reinstall to the user rather than retrying in-session. Restarting the monitor launcher can also make it quit and relaunch the Codex app, so prefer verifying over restarting.

After verification, commit the focused changes and push them to the configured GitHub remote unless the user asks to keep the work local or requests review before publishing.

Never commit authentication files, session JSONL files, runtime snapshots, generated history pages, logs, `.DS_Store`, or secrets. Preserve the MIT attribution to Kevin Ke and Ailble.
