"""Build the repository-owned V2 panel from modules and pinned visual resources."""
import argparse
import base64
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
MODULES = (
    'panel_format.js', 'panel_time.js', 'panel_metrics.js', 'panel_geometry.js',
    'panel_companion_behavior.js', 'panel_companion_runtime.js', 'panel_companion_view.js',
    'panel_layout_runtime.js', 'panel_templates.js', 'panel_styles.js', 'panel_language.js',
    'panel_companion_preferences.js', 'panel_layout_data.js', 'panel_layout_preference.js',
    'panel_scale_preference.js', 'panel_edge_preference.js', 'panel_skin_preference.js',
    'panel_controls.js', 'panel_details.js', 'panel_context.js', 'panel_health.js',
    'panel_account_status.js', 'panel_account_windows.js', 'panel_account_overview.js',
    'panel_diagnostics.js', 'panel_samples.js', 'panel_disclosures.js', 'panel_body.js', 'panel_handoff.js',
    'panel_position_reset.js', 'panel_host_details.js', 'panel_mount.js', 'panel_adapter.js',
)


def artwork():
    directory = ROOT / 'assets/companions'
    uri = lambda path: 'data:image/webp;base64,' + base64.b64encode(path.read_bytes()).decode()
    art = {path.stem:uri(path) for path in sorted((directory / 'web').glob('*.webp'))}
    expressions = {'cat':{path.stem.removeprefix('cat-'):uri(path)
                          for path in sorted((directory / 'expressions').glob('cat-*.webp'))}}
    if set(art) != {'candy', 'cat', 'corgi', 'frost', 'mint', 'tea'} or set(expressions['cat']) != {
            'idle', 'happy', 'concerned', 'notice', 'waiting', 'pet'}:
        raise ValueError('incomplete companion artwork')
    return art, expressions


def resource_hashes():
    """Return reproducible hashes for every bundled visual input."""
    directory = ROOT / 'assets' / 'companions'
    paths = sorted(directory.glob('web/*.webp')) + sorted(directory.glob('expressions/*.webp'))
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths}


def build():
    root = ROOT / 'quota_monitor'
    script = (root / 'panel_shell.js').read_text()
    script += ''.join((root / name).read_text() for name in MODULES)
    art, expressions = artwork()
    replacements = {
        '__COMPANION_ART__': art,
        '__COMPANION_EXPRESSIONS__': expressions,
    }
    for marker, value in replacements.items():
        if script.count(marker) != 1:
            raise ValueError('unexpected resource marker')
        script = script.replace(marker, value if isinstance(value, str) else json.dumps(value))
    header = ('// V2 repository-owned panel; attributed visual resources.\n'
              '// Copyright (c) 2026 Kevin Ke; Copyright (c) 2026 Ailble.\n'
              '// MIT: accompanying LICENSE and NOTICE must travel with this file.\n')
    return header + script


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output_dir', type=Path)
    args = parser.parse_args()
    script = build()
    args.output_dir.mkdir()
    (args.output_dir / 'consumer.js').write_text(script, encoding='utf-8')
    for name in ('LICENSE', 'NOTICE'):
        (args.output_dir / name).write_text((ROOT / name).read_text(), encoding='utf-8')
    manifest = {'consumer': {'path':'consumer.js', 'sha256':hashlib.sha256(script.encode()).hexdigest()},
                'visualResources':'assets/companions',
                'visualResourceSHA256': resource_hashes(),
                'status':'independent-v2-candidate'}
    (args.output_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
