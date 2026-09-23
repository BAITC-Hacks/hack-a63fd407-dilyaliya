"""One-command bootstrap. Default installation is strictly offline."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    args = sys.argv[1:]
    online = '--online' in args
    args = [arg for arg in args if arg != '--online']
    python = ROOT / '.venv' / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    if not python.exists():
        if not (3, 11) <= sys.version_info[:2] <= (3, 13):
            raise SystemExit('Use Python 3.11-3.13. Included Windows wheels require Python 3.12 x64.')
        subprocess.run([sys.executable, '-m', 'venv', str(ROOT / '.venv')], check=True)
    requirements = ROOT / 'requirements.txt'
    check = ('import importlib.metadata as m,sys; from pathlib import Path; '
             'pins=[s.split("==") for s in Path(sys.argv[1]).read_text().splitlines() if s.strip()]; '
             'sys.exit(0 if all(m.version(n)==v for n,v in pins) else 1)')
    ready = subprocess.run([str(python), '-c', check, str(requirements)], capture_output=True).returncode == 0
    if not ready:
        wheels = ROOT / 'wheelhouse'
        if not online and not any(wheels.glob('*.whl')):
            raise SystemExit('Offline dependencies missing: unpack the submission bundle with wheelhouse/, '
                             'or prepare dependencies beforehand using: python run.py --online')
        command = [str(python), '-m', 'pip', 'install', '--disable-pip-version-check']
        if not online:
            command += ['--no-index', '--find-links', str(wheels)]
        command += ['-r', str(requirements)]
        subprocess.run(command, check=True, cwd=ROOT)
    subprocess.run([str(python), '-X', 'utf8', str(ROOT / 'run_pipeline.py'), *args], check=True, cwd=ROOT)


if __name__ == '__main__':
    main()
