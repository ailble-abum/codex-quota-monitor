"""Explicit trusted renderer input; digest pins bytes, not their safety/source."""
import hashlib
import os
from pathlib import Path
import re
import stat


def load_consumer(config):
    if (not isinstance(config, dict) or set(config) != {'path', 'sha256'}
            or not isinstance(config['sha256'], str)
            or not re.fullmatch('[0-9a-f]{64}', config['sha256'])):
        raise ValueError('invalid consumer config')
    descriptor = os.open(Path(config['path']), os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('consumer must be regular file')
        data = stream.read(524289)
    if not data or len(data) > 524288 or hashlib.sha256(data).hexdigest() != config['sha256']:
        raise ValueError('invalid consumer bytes')
    return {'source': data.decode('utf-8'), 'digest': config['sha256']}
