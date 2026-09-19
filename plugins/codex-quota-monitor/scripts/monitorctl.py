"""Manage this plugin's macOS LaunchAgent without affecting other services."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import time

LABEL = 'local.codex-quota-monitor'
SERVICE = f'gui/{os.getuid() if hasattr(os,"getuid") else 0}/{LABEL}'
PLIST = Path.home() / 'Library/LaunchAgents' / f'{LABEL}.plist'
SCRIPTS = Path(__file__).resolve().parent


def run(*args):
    return subprocess.run(args, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'start', 'stop', 'status', 'doctor', 'reset-position', 'show'])
    args = parser.parse_args()
    if sys.platform == 'win32':
        from windows_monitor import manage, WindowsAdapterError
        try:
            result=manage(args.action)
        except (WindowsAdapterError,OSError,ValueError) as exc:
            raise SystemExit(str(exc))
        print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
        if not result.get('ok',True):raise SystemExit(1)
        return
    if args.action == 'install':
        runtime = Path.home() / 'Library/Application Support/CodexQuotaMonitor/scripts'
        runtime.parent.mkdir(parents=True,exist_ok=True)
        binary = runtime.parent/'quota-menu'
        built = runtime.parent/'quota-menu.new'
        result = run('/usr/bin/swiftc', str(SCRIPTS/'QuotaMenu.swift'), '-o', str(built))
        if result.returncode:
            raise SystemExit(result.stderr)
        built.replace(binary)
        run('launchctl', 'bootout', f'gui/{os.getuid()}/local.codex-quota-menu')
        menu_plist = PLIST.with_name('local.codex-quota-menu.plist')
        with menu_plist.open('wb') as handle:
            plistlib.dump({'Label':'local.codex-quota-menu','ProgramArguments':[str(binary)],
                          'RunAtLoad':True,'KeepAlive':True,'ThrottleInterval':30},handle)
        for _ in range(5):
            result=run('launchctl','bootstrap',f'gui/{os.getuid()}',str(menu_plist))
            if result.returncode==0:break
            time.sleep(.5)
        if result.returncode:raise SystemExit(result.stderr)
        run('launchctl', 'bootout', SERVICE)
        if runtime.resolve() != SCRIPTS:
            shutil.copytree(SCRIPTS, runtime, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
        config = {'Label': LABEL, 'ProgramArguments': ['/bin/bash', str(runtime/'start_codex_monitor.sh'),
                  '9222', '--no-reopen-after-quit'], 'RunAtLoad': True, 'KeepAlive': True,
                  'ThrottleInterval': 30, 'EnvironmentVariables': {'PATH': '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
                  'PYTHONUNBUFFERED': '1'}, 'StandardOutPath': '/tmp/codex-quota-monitor-service.log',
                  'StandardErrorPath': '/tmp/codex-quota-monitor-service.log'}
        PLIST.parent.mkdir(parents=True, exist_ok=True)
        with PLIST.open('wb') as handle:
            plistlib.dump(config, handle)
        # launchd may still be disposing the old service after bootout returns.
        for attempt in range(5):
            result = run('launchctl', 'bootstrap', f'gui/{os.getuid()}', str(PLIST))
            if result.returncode == 0:
                break
            time.sleep(.5)
        if result.returncode:
            raise SystemExit(result.stderr)
        print('Installed service: '+str(runtime))
        return
    if args.action == 'start':
        if not PLIST.exists():
            raise SystemExit('LaunchAgent not installed')
        if run('launchctl', 'print', SERVICE).returncode:
            result = run('launchctl', 'bootstrap', f'gui/{os.getuid()}', str(PLIST))
        else:
            result = run('launchctl', 'kickstart', '-k', SERVICE)
        if result.returncode:
            raise SystemExit(result.stderr)
        menu_plist=PLIST.with_name('local.codex-quota-menu.plist')
        if menu_plist.exists() and run('launchctl','print',f'gui/{os.getuid()}/local.codex-quota-menu').returncode:
            run('launchctl','bootstrap',f'gui/{os.getuid()}',str(menu_plist))
        print('Monitor service started')
        return
    if args.action == 'stop':
        run('launchctl', 'bootout', SERVICE)
        run('launchctl', 'bootout', f'gui/{os.getuid()}/local.codex-quota-menu')
    if args.action in ('stop', 'reset-position', 'show'):
        import context_token_injector as injector
        try:
            client = injector.CDPClient(injector.select_target(injector.devtools_targets(9222))['webSocketDebuggerUrl'])
            if args.action == 'stop':
                expression = """window.__codexContextTokenInspectorObserver?.disconnect();
                document.getElementById('codex-context-token-inspector-root')?.__ctiRemoveResize?.();
                document.getElementById('codex-context-token-inspector-root')?.__ctiClearHint?.();
                clearTimeout(window.__codexContextTokenInspectorDetailTimer);
                cancelIdleCallback(window.__codexContextTokenInspectorIdleCallback || 0);
                document.querySelectorAll('#codex-context-token-inspector-root,#codex-context-token-inspector-style,[data-context-token-chip],[data-context-token-footer],[data-context-token-badge]').forEach(n=>n.remove());
                window.__codexContextTokenInspectorRuntimeVersion=null; true"""
            else:
                expression = """localStorage.removeItem('codex-context-token-inspector-position');
                localStorage.removeItem('cti-layout-v2');
                (()=>{const n=document.getElementById('codex-context-token-inspector-root');if(n){n.__ctiLayout={};n.style.left='14px';n.style.top='auto';n.style.bottom='16px';}})(); true"""
                if args.action=='show':
                    expression = """(()=>{const n=document.getElementById('codex-context-token-inspector-root');
                    if(n?.getAttribute('data-collapsed')==='true')n.querySelector('[data-cti-toggle]')?.click();
                    return !!n;})();true"""
            client.evaluate(expression)
            client.close()
        except Exception:
            print('Display not connected; service operation completed')
        return
    status = run('launchctl', 'print', SERVICE)
    print('Service: '+('running' if 'state = running' in status.stdout else 'not running'))
    menu = run('launchctl','print',f'gui/{os.getuid()}/local.codex-quota-menu')
    print('Menu bar: '+('running' if 'state = running' in menu.stdout else 'not running'))
    if PLIST.exists():
        with PLIST.open('rb') as handle:
            config = plistlib.load(handle)
        print('Launcher: '+config['ProgramArguments'][1])
    if args.action == 'doctor':
        import context_token_injector as injector
        from quota_reader import read_quota
        try:
            target = injector.select_target(injector.devtools_targets(9222))
            client = injector.CDPClient(target['webSocketDebuggerUrl'])
            print('Display: '+str(client.evaluate("!!document.getElementById('codex-context-token-inspector-root')")))
            client.close()
        except Exception as exc:
            print('Display: unavailable ('+type(exc).__name__+')')
        try:
            print('Quota: '+json.dumps(read_quota(), ensure_ascii=False))
        except Exception as exc:
            print('Quota: unavailable ('+type(exc).__name__+')')
        history=Path.home()/'Library/Application Support/CodexQuotaMonitor/history.json'
        print('History: '+('available' if history.exists() else 'awaiting first sample'))


if __name__ == '__main__':
    main()
