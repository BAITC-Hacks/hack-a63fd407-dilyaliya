"""Verify a clean offline installation and byte-for-byte result reproducibility."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
from time import perf_counter
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main():
    verification = ROOT / '.verification'
    verification.mkdir(exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix='offline-', dir=verification))
    with ZipFile(ROOT / 'hackalem-offline-win-py312.zip') as archive:
        for name in archive.namelist():
            if not (target / name).resolve().is_relative_to(target.resolve()):
                raise ValueError('Archive member is outside the destination')
        archive.extractall(target)
    manifest = json.loads((target / 'SHA256SUMS.json').read_text(encoding='utf-8'))
    for name, expected in manifest.items():
        if hashlib.sha256((target / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Checksum mismatch: {name}')
    start = perf_counter()
    # Default run.py invokes pip with --no-index; no copied venv is available.
    result = subprocess.run([sys.executable, '-X', 'utf8', str(target / 'run.py'), '--out', str(target / 'fresh-output')],
                            cwd=target, capture_output=True, text=True, encoding='utf-8', errors='replace')
    (ROOT / '.verification/offline-install.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    result.check_returncode()
    compared = ['nodes_roles.csv', 'clusters.csv', 'top_nodes.csv', 'ranking_sensitivity.csv', 'graph.html']
    for name in compared:
        if (target / 'fresh-output' / name).read_bytes() != (target / 'output' / name).read_bytes():
            raise ValueError(f'Result differs: {name}')
    report = {'clean_install_and_run_seconds': round(perf_counter()-start, 3),
              'manifest_files_verified': len(manifest), 'identical_outputs': compared,
              'pip_mode': '--no-index --find-links wheelhouse', 'python': sys.version.split()[0]}
    (ROOT / '.verification/offline-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
