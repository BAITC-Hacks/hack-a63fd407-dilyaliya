from importlib.metadata import version
from pathlib import Path
import sys
try:
    if sys.version_info[:2] != (3,11):
        raise ValueError("CPython 3.11 required")
    for line in (Path(__file__).resolve().parents[1]/'requirements.txt').read_text().splitlines():
        if line.strip() and not line.startswith('#'):
            package, expected = line.strip().split('==')
            if version(package) != expected:
                raise ValueError(package)
except Exception:
    sys.exit(1)
