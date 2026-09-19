"""Check whether a newer plugin build is published on GitHub.

The plugin declares its version in ``.codex-plugin/plugin.json`` as
``0.1.0+codex.<utc-timestamp>``. The cachebuster (the ``codex.<timestamp>``
suffix) is what Codex keys its cache directory on, and it is monotonically
increasing, so comparing cachebusters is the authoritative "is there an update"
test. The check only ever GETs the public raw plugin.json; it sends no local
version or identity, and a failure degrades silently to "unavailable" so the
overlay keeps working offline.

Steady-state rechecks are throttled to once a day. raw.githubusercontent.com
serves plain files, not the rate-limited API, so this is far below any limit.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.request

from platform_paths import runtime_root

RAW_MANIFEST_URL = (
    "https://raw.githubusercontent.com/ailble-abum/codex-quota-monitor/"
    "main/plugins/codex-quota-monitor/.codex-plugin/plugin.json"
)
RELEASES_URL = "https://github.com/ailble-abum/codex-quota-monitor/releases"
RECHECK_INTERVAL = 24 * 3600
REQUEST_TIMEOUT = 10
USER_AGENT = "codex-quota-monitor"


def split_version(version):
    """Return (semver, cachebuster) for a 'x.y.z+codex.<timestamp>' string."""
    if not isinstance(version, str):
        return (None, None)
    semver, _, cachebuster = version.partition("+")
    return (semver.strip() or None, cachebuster.strip() or None)


def is_valid_version(version):
    """True only for a plausible 'x.y.z[+codex.<digits>]' declaration.

    The semver part has to be three dotted numeric groups, otherwise a stray
    string would parse as (0,0,0) and read as "up to date" instead of being
    rejected outright.
    """
    semver, cachebuster = split_version(version)
    if not semver:
        return False
    groups = semver.split(".")
    if len(groups) != 3 or not all(group.isdigit() for group in groups):
        return False
    if cachebuster is not None and cachebuster_stamp(cachebuster) is None:
        return False
    return True


def cachebuster_stamp(cachebuster):
    """The numeric timestamp inside 'codex.<digits>', or None when malformed."""
    if not isinstance(cachebuster, str) or not cachebuster.startswith("codex."):
        return None
    digits = cachebuster[len("codex."):]
    return int(digits) if digits.isdigit() else None


def _semver_tuple(semver):
    if not isinstance(semver, str):
        return None
    parts = []
    for part in semver.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer(local, remote):
    """True when ``remote`` is a newer build than ``local``.

    The cachebuster timestamp is authoritative because it always increases.
    When either side lacks one, fall back to semver; a side that cannot be
    parsed is treated as "not newer" rather than "older".
    """
    local_semver, local_cache = split_version(local)
    remote_semver, remote_cache = split_version(remote)
    local_stamp = cachebuster_stamp(local_cache)
    remote_stamp = cachebuster_stamp(remote_cache)
    if local_stamp is not None and remote_stamp is not None:
        return remote_stamp > local_stamp
    local_tuple = _semver_tuple(local_semver)
    remote_tuple = _semver_tuple(remote_semver)
    if local_tuple is not None and remote_tuple is not None:
        return remote_tuple > local_tuple
    return False


def read_local_version():
    """The (version, cachebuster) the installer last recorded, or (None, None)."""
    try:
        info = json.loads((runtime_root() / "build_info.json").read_text(encoding="utf-8"))
        info = info if isinstance(info, dict) else {}
    except (OSError, ValueError):
        info = {}
    return (info.get("pluginVersion"), info.get("cachebuster"))


def fetch_remote_version():
    """The declared version string in the published plugin.json."""
    request = urllib.request.Request(RAW_MANIFEST_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        data = response.read()
    manifest = json.loads(data.decode("utf-8"))
    return manifest.get("version")


def _unavailable(current, latest):
    return {"status": "unavailable", "current": current, "latest": latest,
            "latestSemver": None, "url": RELEASES_URL, "checkedAt": int(time.time())}


def check_for_update():
    """Compare the published version against the installed one.

    Returns a dict whose ``status`` is one of ``update_available``,
    ``up_to_date``, or ``unavailable``. It never raises: network or parse
    failures fall back to ``unavailable`` so callers can ignore the result.
    """
    local_plugin, local_cache = read_local_version()
    try:
        remote = fetch_remote_version()
    except Exception:
        return _unavailable(local_plugin, None)
    if not is_valid_version(remote):
        return _unavailable(local_plugin, None)
    remote_semver, _ = split_version(remote)
    local_full = f"{local_plugin}+{local_cache}" if local_plugin and local_cache else local_plugin
    if not is_valid_version(local_full):
        return _unavailable(local_plugin, remote)
    if is_newer(local_full, remote):
        return {"status": "update_available", "current": local_plugin, "latest": remote,
                "latestSemver": remote_semver, "url": RELEASES_URL, "checkedAt": int(time.time())}
    return {"status": "up_to_date", "current": local_plugin, "latest": remote,
            "latestSemver": remote_semver, "url": RELEASES_URL, "checkedAt": int(time.time())}


class UpdateChecker:
    """Background, throttled update check mirroring the quota reader's shape.

    ``snapshot()`` returns the last known result and kicks off a recheck when
    the throttle allows, without blocking the injection loop.
    """

    def __init__(self):
        self.value = {"status": "checking"}
        self.next_check = 0.0
        self.busy = False
        self.lock = threading.Lock()

    def snapshot(self):
        with self.lock:
            if not self.busy and time.monotonic() >= self.next_check:
                self.busy = True
                threading.Thread(target=self._refresh, daemon=True).start()
            return dict(self.value)

    def _refresh(self):
        try:
            value = check_for_update()
        except Exception:
            value = {"status": "unavailable", "current": None, "latest": None,
                     "latestSemver": None, "url": RELEASES_URL, "checkedAt": int(time.time())}
        with self.lock:
            self.value = value
            self.next_check = time.monotonic() + RECHECK_INTERVAL
            self.busy = False


if __name__ == "__main__":
    print(json.dumps(check_for_update(), ensure_ascii=False))
