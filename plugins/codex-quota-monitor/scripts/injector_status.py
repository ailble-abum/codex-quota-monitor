"""Owner-only health marker shared by the injector, menu bar, and doctor."""
import json
import sys
import time
from pathlib import Path

from platform_paths import runtime_root
from usage_history import atomic

STATUS_FILE = "injector_status.json"


def write_status(status, error_code=None, root=None):
    value = {"status": status, "updatedAt": time.time()}
    if error_code:
        value["errorCode"] = error_code
    atomic(Path(root or runtime_root()) / STATUS_FILE, json.dumps(value))
    return value


def read_status(root=None):
    try:
        value = json.loads((Path(root or runtime_root()) / STATUS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"status": "unknown"}
    return value if isinstance(value, dict) else {"status": "unknown"}


if __name__ == "__main__":
    write_status(sys.argv[1] if len(sys.argv) > 1 else "unknown",
                 sys.argv[2] if len(sys.argv) > 2 else None)
