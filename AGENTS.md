# Repository maintenance

For requested changes to this repository, update the source under `plugins/codex-quota-monitor`, run the Python tests and Swift typecheck, update the plugin cachebuster, reinstall the local plugin, and verify `monitorctl.py doctor` when the change affects runtime behavior.

After verification, commit the focused changes and push them to the configured GitHub remote unless the user asks to keep the work local or requests review before publishing.

Never commit authentication files, session JSONL files, runtime snapshots, generated history pages, logs, `.DS_Store`, or secrets. Preserve the MIT attribution to Kevin Ke and Ailble.
