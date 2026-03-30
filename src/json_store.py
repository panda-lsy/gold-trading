#!/usr/bin/env python3
"""
JSON 文件持久化工具。
提供跨进程文件锁与原子写入能力。
"""
import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def file_lock(lock_path: str, timeout_seconds: float = 5.0, poll_seconds: float = 0.05):
    """通过 lock 文件实现简单跨进程互斥。"""
    start = time.time()
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            break
        except FileExistsError:
            if time.time() - start > timeout_seconds:
                raise TimeoutError(f'Failed to acquire file lock: {lock_path}')
            time.sleep(poll_seconds)

    try:
        yield
    finally:
        os.close(fd)
        try:
            os.remove(lock_path)
        except OSError:
            pass


def load_json_file(file_path: str, default):
    """安全加载 JSON，异常时返回 default。"""
    path = Path(file_path)
    lock_path = str(path) + '.lock'

    if not path.exists():
        return default

    try:
        with file_lock(lock_path):
            if not path.exists():
                return default
            with path.open('r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        return default


def save_json_file(file_path: str, data, indent=None, ensure_ascii=False):
    """原子写 JSON，防止部分写入导致文件损坏。"""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = str(path) + '.lock'

    with file_lock(lock_path):
        fd, temp_path = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=str(path.parent))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, str(path))
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
