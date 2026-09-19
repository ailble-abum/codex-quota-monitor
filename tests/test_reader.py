import json
import os
import tempfile
import unittest
from pathlib import Path

from quota_monitor.reader import JournalReader


class JournalReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'synthetic.jsonl'
        self.path.touch()
        self.reader = JournalReader(self.path, read_budget=32, line_limit=64)

    def drain(self):
        rows = []
        for _ in range(100):
            batch = self.reader.poll()
            rows.extend(batch.records)
            if not batch.more:
                return rows
        self.fail('reader did not reach the snapshot end')

    def test_append_is_delivered_once_and_idle_reads_no_new_bytes(self):
        self.path.write_bytes(b'{"n":1}\n')
        self.assertEqual(self.drain(), [{'n': 1}])
        self.assertEqual(self.reader.poll().bytes_read, 0)
        with self.path.open('ab') as stream:
            stream.write(b'{"n":2}\n')
        batch = self.reader.poll()
        self.assertEqual(batch.records, [{'n': 2}])
        self.assertEqual(batch.bytes_read, 8)
        self.assertEqual(self.drain(), [])

    def test_partial_utf8_and_json_wait_for_newline(self):
        data = json.dumps({'s': '猫'}, ensure_ascii=False).encode() + b'\n'
        cut = data.index('猫'.encode()) + 1
        self.path.write_bytes(data[:cut])
        self.assertEqual(self.drain(), [])
        with self.path.open('ab') as stream:
            stream.write(data[cut:])
        self.assertEqual(self.drain(), [{'s': '猫'}])

    def test_pending_survives_unavailability_then_clears_on_newline(self):
        self.path.write_bytes(b'{"n":1}')
        self.assertTrue(self.reader.poll().pending)
        parked = self.path.with_suffix('.parked')
        self.path.rename(parked)
        batch = self.reader.poll()
        self.assertEqual(batch.status, 'unavailable')
        self.assertTrue(batch.pending)
        parked.rename(self.path)
        with self.path.open('ab') as stream:
            stream.write(b'\n')
        batch = self.reader.poll()
        self.assertFalse(batch.pending)
        self.assertEqual(batch.records, [{'n': 1}])

    def test_invalid_lines_are_counted_without_exposing_content(self):
        self.path.write_bytes(b'not-secret-json\n[]\n\xff\n{"n":3}\n')
        batch = self.reader.poll()
        self.assertEqual(batch.records, [{'n': 3}])
        self.assertEqual(batch.invalid_lines, 3)
        self.assertNotIn('secret', repr(batch))

    def test_budget_bounds_one_poll(self):
        self.path.write_bytes(b'{"n":1}\n' * 10)
        batch = self.reader.poll()
        self.assertEqual(batch.bytes_read, 32)
        self.assertTrue(batch.more)
        self.assertEqual(len(batch.records) + len(self.drain()), 10)

    def test_oversized_line_is_discarded_until_delimiter(self):
        self.path.write_bytes(b'x' * 150 + b'\n{"n":4}\n')
        rows, invalid = [], 0
        for _ in range(10):
            batch = self.reader.poll()
            rows.extend(batch.records)
            invalid += batch.invalid_lines
            if not batch.more:
                break
        self.assertEqual(rows, [{'n': 4}])
        self.assertEqual(invalid, 1)

    def test_replacement_resets_even_at_same_size(self):
        self.path.write_bytes(b'{"n":1}\n')
        self.drain()
        replacement = self.path.with_suffix('.new')
        replacement.write_bytes(b'{"n":2}\n')
        replacement.replace(self.path)
        batch = self.reader.poll()
        self.assertTrue(batch.reset)
        self.assertEqual(batch.records, [{'n': 2}])

    def test_truncation_discards_pending_fragment(self):
        self.path.write_bytes(b'{"n":1}\n{"unfinished":')
        self.drain()
        self.path.write_bytes(b'{"n":2}\n')
        batch = self.reader.poll()
        self.assertTrue(batch.reset)
        self.assertEqual(batch.records, [{'n': 2}])

    def test_missing_file_preserves_cursor_and_reports_unavailable(self):
        missing = JournalReader(self.path.with_name('absent'))
        batch = missing.poll()
        self.assertEqual(batch.status, 'unavailable')
        self.assertEqual(batch.records, [])
        self.assertEqual(batch.bytes_read, 0)

    def test_two_readers_do_not_share_state(self):
        other = JournalReader(self.path)
        self.path.write_bytes(b'{"n":1}\n')
        self.assertEqual(self.drain(), [{'n': 1}])
        self.assertEqual(other.poll().records, [{'n': 1}])

    def test_strict_json_rejects_nonfinite_values(self):
        self.path.write_bytes(b'{"n":NaN}\n{"n":Infinity}\n')
        batch = self.reader.poll()
        self.assertEqual(batch.records, [])
        self.assertEqual(batch.invalid_lines, 2)

    def test_positive_limits_required(self):
        for kwargs in ({'read_budget': 0}, {'line_limit': 0}):
            with self.assertRaises(ValueError):
                JournalReader(self.path, **kwargs)

    def test_missing_then_restored_file_retains_pending_bytes(self):
        self.path.write_bytes(b'{"n":')
        self.drain()
        parked = self.path.with_suffix('.parked')
        self.path.rename(parked)
        self.assertEqual(self.reader.poll().status, 'unavailable')
        parked.rename(self.path)
        with self.path.open('ab') as stream:
            stream.write(b'7}\n')
        self.assertEqual(self.drain(), [{'n': 7}])

    def test_crlf_and_empty_lines(self):
        self.path.write_bytes(b'\r\n \n{"n":8}\r\n')
        batch = self.reader.poll()
        self.assertEqual(batch.records, [{'n': 8}])
        self.assertEqual(batch.invalid_lines, 0)

    def test_float_overflow_is_not_exported_as_infinity(self):
        self.path.write_bytes(b'{"n":1e999}\n')
        batch = self.reader.poll()
        self.assertEqual(batch.records, [])
        self.assertEqual(batch.invalid_lines, 1)

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'POSIX pipe check')
    def test_fifo_returns_without_waiting_for_a_writer(self):
        fifo = self.path.with_suffix('.fifo')
        os.mkfifo(fifo)
        self.assertEqual(JournalReader(fifo).poll().status, 'unavailable')


if __name__ == '__main__':
    unittest.main()
