"""Package all five CPython 3.11 wheel sets without personal environments."""
from pathlib import Path
import hashlib
import json
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def main():
    if not (ROOT / 'vendor/wheels/manifest.json').exists():
        raise SystemExit('Missing vendor/wheels/manifest.json; copy the complete vendor directory.')
    names = ['README.md', 'requirements.txt', 'run.py', 'run.bat', 'run.sh', 'launch.py',
             'run_pipeline.py', 'serve.py', '.gitignore', '.dockerignore', 'Dockerfile', 'compose.yaml']
    files = [ROOT / name for name in names]
    for folder in ['app', 'pipeline', 'tests', 'tools', 'scripts', 'data', 'output', 'docs', 'vendor', 'starter']:
        files.extend(p for p in (ROOT / folder).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix != '.pyc' and p.name != '.DS_Store')
    files = sorted(set(files))
    manifest = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    target = ROOT / 'hackalem-offline-py311.zip'
    with ZipFile(target, 'w', ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.writestr('SHA256SUMS.json', json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f'{target.name}: {target.stat().st_size / 1024**2:.1f} MiB, {len(files)} files')


if __name__ == '__main__':
    main()
