"""Offline bounded preview; paths and raw journal records are never printed."""
import argparse
import json

from .compat import panel_payload, thread_key
from .journal import SessionJournal


def main():
    parser = argparse.ArgumentParser(description='Preview one explicitly selected session journal')
    parser.add_argument('path')
    parser.add_argument('--thread', required=True, help='Verified owner of this file; no discovery is performed')
    parser.add_argument('--max-polls', type=int, default=64)
    args = parser.parse_args()
    key = thread_key(args.thread)
    if key is None or not 1 <= args.max_polls <= 4096:
        parser.error('invalid thread identifier or max-polls outside 1..4096')
    journal = SessionJournal(args.path)
    bytes_read = invalid = 0
    for _ in range(args.max_polls):
        reading = journal.poll()
        bytes_read += reading['bytes_read']
        invalid += reading['invalid_lines']
        if reading['status'] != 'ok' or not reading['more']:
            break
    status = reading['status'] if not reading['more'] else 'incomplete'
    output = {'status': status, 'bytes_read': bytes_read, 'invalid_lines': invalid,
              'payload': panel_payload({key: reading}, key)}
    print(json.dumps(output, ensure_ascii=False, allow_nan=False))
    return 0 if status == 'ok' else 2


if __name__ == '__main__':
    raise SystemExit(main())
