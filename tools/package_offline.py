"""Package source, data, results and prepared wheels without personal environments."""
from pathlib import Path
import hashlib
import json
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def main():
    wheels = sorted((ROOT / 'wheelhouse').glob('*.whl'))
    if not wheels:
        raise SystemExit('Prepare wheelhouse first; see README.')
    files = [ROOT / name for name in ['README.md', 'requirements.txt', 'run.py', 'run.bat', 'run.sh', 'run_pipeline.py', '.gitignore']]
    for folder in ['app', 'pipeline', 'tests', 'tools', 'data', 'output', 'docs', 'wheelhouse', 'starter']:
        files.extend(p for p in (ROOT / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    files = sorted(set(files))
    manifest = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    target = ROOT / 'hackalem-offline-win-py312.zip'
    with ZipFile(target, 'w', ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT))
        archive.writestr('SHA256SUMS.json', json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f'{target.name}: {target.stat().st_size / 1024**2:.1f} MiB, {len(files)} files')


if __name__ == '__main__':
    main()
