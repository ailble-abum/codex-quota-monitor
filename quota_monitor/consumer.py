"""Explicit trusted renderer input; digest pins bytes, not their safety/source."""
import hashlib
import os
from pathlib import Path
import re
import stat

MAX_CONSUMER_BYTES = 8 * 1024 * 1024


def load_consumer(config):
    if (not isinstance(config, dict) or set(config) != {'path', 'sha256'}
            or not isinstance(config['sha256'], str)
            or not re.fullmatch('[0-9a-f]{64}', config['sha256'])):
        raise ValueError('invalid consumer config')
    descriptor = os.open(Path(config['path']), os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('consumer must be regular file')
        data = stream.read(MAX_CONSUMER_BYTES + 1)
    if not data or len(data) > MAX_CONSUMER_BYTES or hashlib.sha256(data).hexdigest() != config['sha256']:
        raise ValueError('invalid consumer bytes')
    return {'source': data.decode('utf-8'), 'digest': config['sha256']}
