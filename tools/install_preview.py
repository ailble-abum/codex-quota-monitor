"""Install an attributed V2 preview into a NEW directory; no service or host changes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile


def install(candidate, destination):
    candidate, destination = Path(candidate), Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError('destination_exists')
    manifest = json.loads((candidate / 'manifest.json').read_text())
    if (not isinstance(manifest, dict) or not isinstance(manifest.get('consumer'), dict)
            or 'sha256' not in manifest['consumer']):
        raise ValueError('invalid_candidate')
    script = (candidate / 'consumer.js').read_bytes()
    if (len(script) > 8 * 1024 * 1024 or manifest.get('status') not in {
            'derived-isolated-candidate', 'independent-v2-candidate'}
            or hashlib.sha256(script).hexdigest() != manifest['consumer']['sha256']):
        raise ValueError('invalid_candidate')
    # Read required attribution before creating anything at the destination.
    attribution = {name: (candidate / name).read_bytes() for name in ('LICENSE', 'NOTICE')}
    repository = Path(__file__).resolve().parents[1]
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.quota-v2-', dir=destination.parent))
    try:
        shutil.copytree(repository / 'quota_monitor', stage / 'quota_monitor',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copyfile(repository / 'requirements-cdp.txt', stage / 'requirements-cdp.txt')
        (stage / 'renderer').mkdir()
        (stage / 'renderer/consumer.js').write_bytes(script)
        for name, data in attribution.items():
            (stage / 'renderer' / name).write_bytes(data)
        (stage / 'renderer/manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (stage / 'run.py').write_text('from quota_monitor.live import main\nraise SystemExit(main())\n')
        config = {'origin': 'http://127.0.0.1:9222', 'page_url': 'REPLACE_WITH_EXPLICIT_PAGE_URL',
                  'session_root': 'REPLACE_WITH_AUTHORIZED_SESSION_DIRECTORY',
                  'host': 'codex-sidebar', 'panel': True,
                  'consumer': {'path': 'renderer/consumer.js', 'sha256': manifest['consumer']['sha256']}}
        (stage / 'config.example.json').write_text(json.dumps(config, indent=2) + '\n')
        (stage / 'PREVIEW.txt').write_text(
            'V2 预览版：非正式发行，保留 renderer 来源归因。\n'
            '安装依赖：python -m pip install -r requirements-cdp.txt\n'
            '复制并填写 config.example.json；可添加 account_cli 指定 Codex 可执行文件绝对路径。\n'
            '运行：python run.py --config /absolute/config.json\n'
            '不会注册服务、自启动、重启宿主或替换现用版。\n'
            '同一页面只能有一个监视器；请先用隔离页面验收。\n'
            '停止：Ctrl+C；退出会释放本实例页面状态。卸载：退出后删除本目录。\n')
        hashes = {str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(stage.rglob('*')) if p.is_file()}
        (stage / 'install-manifest.json').write_text(json.dumps(
            {'status': 'preview-not-release', 'files': hashes}, indent=2) + '\n')
        # mkdir reserves ownership without replacing an existing directory or symlink.
        destination.mkdir(mode=0o700)
        try:
            for child in stage.iterdir():
                shutil.move(str(child), str(destination / child.name))
        except BaseException:
            shutil.rmtree(destination)
            raise
    finally:
        shutil.rmtree(stage)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate')
    parser.add_argument('destination')
    args = parser.parse_args()
    try:
        install(args.candidate, args.destination)
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(2, 'preview_install_failed\n')
    print('preview_files_installed; runtime_not_started')
