import hashlib
from pathlib import Path
import tempfile
import unittest
from quota_monitor.consumer import MAX_CONSUMER_BYTES, load_consumer


class ConsumerTests(unittest.TestCase):
    def test_verified_bytes_are_frozen_until_runner_restart(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'consumer.js'
            source = b'(empty => { window.fixture = empty; })'
            path.write_bytes(source)
            config = {'path': path, 'sha256': hashlib.sha256(source).hexdigest()}
            loaded = load_consumer(config)
            path.write_text('changed')
            self.assertEqual(loaded['source'], source.decode())
            with self.assertRaises(ValueError):
                load_consumer(config)

    def test_bad_shape_digest_encoding_and_size_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'consumer.js'
            for data in (b'', b'\xff', b'x' * (MAX_CONSUMER_BYTES + 1)):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    load_consumer({'path': path, 'sha256': hashlib.sha256(data).hexdigest()})
            for config in ({}, {'path': path, 'sha256': 'x'}, {'path': path, 'sha256': 'a'*64, 'extra': 1}):
                with self.assertRaises(ValueError):
                    load_consumer(config)

    def test_repository_renderer_is_accepted(self):
        from tools.build_panel import build
        source = build().encode()
        self.assertGreater(len(source), 524288)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'consumer.js'
            path.write_bytes(source)
            loaded = load_consumer({'path': path, 'sha256': hashlib.sha256(source).hexdigest()})
            self.assertEqual(loaded['digest'], hashlib.sha256(source).hexdigest())
