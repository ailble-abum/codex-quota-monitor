"""Runtime files live in the current platform's per-user application-data folder."""
import os
import sys
from pathlib import Path

def runtime_root():
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'AppData/Local')))/'CodexQuotaMonitor'
    if sys.platform == 'darwin':
        return Path.home()/'Library/Application Support/CodexQuotaMonitor'
    return Path(os.environ.get('XDG_STATE_HOME',str(Path.home()/'.local/state')))/'CodexQuotaMonitor'
