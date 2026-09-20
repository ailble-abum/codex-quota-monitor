"""Build the repository-owned V2 panel from modules and pinned visual resources."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

RESOURCE_HASHES = {
    'companion_art.py': 'bf82328005097b4af6df60b5c158f5f15230e0378b2cad06693ced15a5bb1865',
    'companion_expressions.py': '1be738c3a9d7a1965df6cff09c3929ee12a5550b1fb88c893da165888e13138a',
    'LICENSE': '3173384c5ec386cd808211ded2d3634f2521f9a92de981d2a104a2b42b291b40',
    'NOTICE': '5e524e54bbf3d1839d6e695e5adc189e459921e619612e153d9da703c1729267',
}
MODULES = (
    'panel_format.js', 'panel_time.js', 'panel_metrics.js', 'panel_geometry.js',
    'panel_companion_behavior.js', 'panel_companion_runtime.js', 'panel_companion_view.js',
    'panel_layout_runtime.js', 'panel_templates.js', 'panel_styles.js', 'panel_language.js',
    'panel_companion_preferences.js', 'panel_layout_data.js', 'panel_layout_preference.js',
    'panel_scale_preference.js', 'panel_edge_preference.js', 'panel_skin_preference.js',
    'panel_controls.js', 'panel_details.js', 'panel_context.js', 'panel_health.js',
    'panel_account_status.js', 'panel_account_windows.js', 'panel_account_overview.js',
    'panel_diagnostics.js', 'panel_disclosures.js', 'panel_body.js', 'panel_handoff.js',
    'panel_position_reset.js', 'panel_mount.js', 'panel_adapter.js',
)


def literal(source, name):
    for node in ast.parse(source).body:
        targets = node.targets if isinstance(node, ast.Assign) else (
            [node.target] if isinstance(node, ast.AnnAssign) else [])
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            return ast.literal_eval(node.value)
    raise ValueError('resource constant missing')


def read_resources(directory):
    texts = {}
    for name, digest in RESOURCE_HASHES.items():
        try:
            data = (Path(directory) / name).read_bytes()
        except OSError as error:
            raise ValueError('resource missing') from error
        if len(data) > 1048576 or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('unrecognized resource revision')
        texts[name] = data.decode('utf-8')
    return texts


def build(directory):
    texts = read_resources(directory)
    root = Path(__file__).parents[1] / 'quota_monitor'
    script = (root / 'panel_shell.js').read_text()
    script += ''.join((root / name).read_text() for name in MODULES)
    replacements = {
        '__COMPANION_ART__': literal(texts['companion_art.py'], 'COMPANION_ART'),
        '__COMPANION_EXPRESSIONS__': literal(texts['companion_expressions.py'], 'COMPANION_EXPRESSIONS'),
    }
    for marker, value in replacements.items():
        if script.count(marker) != 1:
            raise ValueError('unexpected resource marker')
        script = script.replace(marker, value if isinstance(value, str) else json.dumps(value))
    header = ('// V2 repository-owned panel; attributed visual resources.\n'
              '// Copyright (c) 2026 Kevin Ke; Copyright (c) 2026 Ailble.\n'
              '// MIT: accompanying LICENSE and NOTICE must travel with this file.\n')
    return header + script, texts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('resource_dir', type=Path)
    parser.add_argument('output_dir', type=Path)
    args = parser.parse_args()
    script, texts = build(args.resource_dir)
    args.output_dir.mkdir()
    (args.output_dir / 'consumer.js').write_text(script, encoding='utf-8')
    for name in ('LICENSE', 'NOTICE'):
        (args.output_dir / name).write_text(texts[name], encoding='utf-8')
    manifest = {'consumer': {'path':'consumer.js', 'sha256':hashlib.sha256(script.encode()).hexdigest()},
                'visualResourceSHA256': RESOURCE_HASHES, 'status':'independent-v2-candidate'}
    (args.output_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
