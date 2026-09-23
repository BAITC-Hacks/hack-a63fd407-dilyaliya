"""Package all five CPython 3.11 wheel sets without personal environments."""
from pathlib import Path
import argparse
import hashlib
import json
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--with-llm', action='store_true', help='Include the installed local model and current-platform engine')
    args = parser.parse_args()
    if not (ROOT / 'vendor/wheels/manifest.json').exists():
        raise SystemExit('Missing vendor/wheels/manifest.json; copy the complete vendor directory.')
    names = ['README.md', 'requirements.txt', 'run.py', 'run.bat', 'run.sh', 'launch.py',
             'run_pipeline.py', 'serve.py', '.gitignore', '.dockerignore', 'Dockerfile', 'compose.yaml']
    files = [ROOT / name for name in names]
    for folder in ['app', 'aml_assistant', 'pipeline', 'tests', 'tools', 'scripts', 'data', 'output', 'docs', 'vendor', 'starter']:
        files.extend(p for p in (ROOT / folder).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix != '.pyc' and p.name != '.DS_Store')
    target = ROOT / 'hackalem-offline-py311.zip'
    if args.with_llm:
        installed = ROOT / '.local_ai/installed.json'
        if not installed.exists():
            raise SystemExit('Prepare the LLM with scripts/setup_llm.py --download first.')
        info = json.loads(installed.read_text(encoding='utf-8'))
        files += [installed, ROOT / '.local_ai' / info['model_path']]
        files += [ROOT / '.local_ai' / path for path in info['runtime_sha256']]
        files += list((ROOT / '.local_ai/licenses').glob('*'))
        target = ROOT / f'hackalem-offline-ai-{info["platform"]}.zip'
    files = sorted(set(files))
    def digest(path):
        value = hashlib.sha256()
        with path.open('rb') as source:
            for chunk in iter(lambda: source.read(8 * 1024**2), b''):
                value.update(chunk)
        return value.hexdigest()
    manifest = {p.relative_to(ROOT).as_posix(): digest(p) for p in files}
    with ZipFile(target, 'w', ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.writestr('SHA256SUMS.json', json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f'{target.name}: {target.stat().st_size / 1024**2:.1f} MiB, {len(files)} files')


if __name__ == '__main__':
    main()
