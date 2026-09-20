import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('audit_release', Path(__file__).parents[1] / 'tools/audit_release.py')
audit_release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_release)


class ReleaseAuditTests(unittest.TestCase):
    def make_bundle(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(root))
        for name in audit_release.REQUIRED:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('ok', encoding='utf-8')
        consumer = root / 'renderer/consumer.js'
        data = b'(() => {})()'
        consumer.write_bytes(data)
        (root / 'renderer/manifest.json').write_text(json.dumps({
            'status': 'independent-v2-candidate',
            'consumer': {'path': 'consumer.js', 'sha256': hashlib.sha256(data).hexdigest()},
        }))
        files = {path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                 for path in audit_release.REQUIRED if path != 'install-manifest.json'}
        (root / 'install-manifest.json').write_text(json.dumps({'files': files}))
        return root

    def test_audits_required_hashes_and_source_markers(self):
        root = self.make_bundle()
        result = audit_release.audit(root)
        self.assertEqual(result['status'], 'audited')
        (root / 'renderer/consumer.js').write_text('context_token_injector.py')
        with self.assertRaises(ValueError):
            audit_release.audit(root)

    def test_rejects_sensitive_material(self):
        root = self.make_bundle()
        (root / 'session.jsonl').write_text('{}')
        with self.assertRaises(ValueError):
            audit_release.audit(root)


if __name__ == '__main__':
    unittest.main()
