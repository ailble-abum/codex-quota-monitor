"""Offline bounded preview; paths and raw journal records are never printed."""
import argparse
import json

from .compat import panel_payload, thread_key
from .journal import SessionJournal
from .discovery import discover


def main():
    parser = argparse.ArgumentParser(description='Preview one explicitly selected session journal')
    parser.add_argument('path')
    parser.add_argument('--thread', required=True, help='Expected task ID, checked against session_meta.id')
    parser.add_argument('--max-polls', type=int, default=64)
    parser.add_argument('--discover', action='store_true', help='Treat path as an explicit journal directory')
    args = parser.parse_args()
    key = thread_key(args.thread)
    if key is None or not 1 <= args.max_polls <= 4096:
        parser.error('invalid thread identifier or max-polls outside 1..4096')
    if args.discover:
        result = discover(args.path, key, max_bytes=args.max_polls * 262144)
        status, reading = result['status'], result['reading']
        bytes_read, invalid = result['bytes_read'], result['invalid_lines']
    else:
        journal = SessionJournal(args.path)
        bytes_read = invalid = 0
        for _ in range(args.max_polls):
            reading = journal.poll()
            bytes_read += reading['bytes_read']
            invalid += reading['invalid_lines']
            if reading['status'] != 'ok' or not reading['more']:
                break
        status = reading['status'] if not reading['more'] else 'incomplete'
        if status == 'ok':
            if reading['identity_status'] != 'verified':
                status = 'identity_' + reading['identity_status']
            elif reading['thread_id'] != key:
                status = 'identity_mismatch'
        reading['status'] = status
    output = {'status': status, 'bytes_read': bytes_read, 'invalid_lines': invalid,
              'payload': panel_payload({key: reading} if reading is not None else {}, key)}
    print(json.dumps(output, ensure_ascii=False, allow_nan=False))
    return 0 if status == 'ok' else 2


if __name__ == '__main__':
    raise SystemExit(main())
