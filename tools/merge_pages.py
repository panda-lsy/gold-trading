#!/usr/bin/env python3
"""
Legacy merge helper.

This repository now treats web/index.html as the single source of truth.
The old inline-template merge script was removed to prevent accidental
regression (stale hardcoded URLs and outdated JS patterns).
"""
from pathlib import Path


def main():
    project_root = Path(__file__).resolve().parents[1]
    index_path = project_root / 'web' / 'index.html'

    if not index_path.exists():
        raise FileNotFoundError(f'Cannot find {index_path}')

    print('web/index.html is already authoritative; no merge action performed.')
    print(f'Checked: {index_path}')


if __name__ == '__main__':
    main()
