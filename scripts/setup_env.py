#!/usr/bin/env python3
"""Проверяемая офлайн-установка для поддерживаемой пары ОС/архитектура."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = {
    ('Darwin','arm64'):'macos-arm64-py311',
    ('Darwin','x86_64'):'macos-x86_64-py311',
    ('Linux','x86_64'):'linux-x86_64-py311',
    ('Linux','arm64'):'linux-aarch64-py311',
    ('Windows','x86_64'):'windows-amd64-py311',
}


def platform_key(system=None, machine=None):
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    machine = {'amd64':'x86_64','aarch64':'arm64'}.get(machine,machine)
    return PLATFORMS.get((system,machine))


def env_python(directory):
    return Path(directory).resolve() / ('Scripts/python.exe' if os.name=='nt' else 'bin/python')


def validate_wheels(root, key):
    root=Path(root)
    manifest_path=root/'manifest.json'
    if not manifest_path.exists():
        raise RuntimeError('Нет vendor/wheels/manifest.json. Скопируйте полный офлайн-комплект.')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    entries={rel:digest for rel,digest in manifest.items() if rel.startswith(key+'/')}
    expected_files={Path(rel).name for rel in entries}
    actual_files={p.name for p in (root/key).glob('*.whl')}
    if not entries or expected_files!=actual_files:
        raise RuntimeError(f'Неполный или изменённый комплект {key}. Проверьте vendor/wheels.')
    for rel,digest in entries.items():
        file=root/rel
        if hashlib.sha256(file.read_bytes()).hexdigest()!=digest:
            raise RuntimeError(f'Повреждён пакет: {rel}')
    return root/key


def setup(directory):
    if platform.python_implementation()!='CPython' or sys.version_info[:2]!=(3,11):
        raise RuntimeError('Для офлайн-запуска нужен CPython 3.11. Используйте python3.11 / py -3.11 или Docker.')
    key=platform_key()
    if not key:
        raise RuntimeError(f'Нет комплекта для {platform.system()} {platform.machine()}. Поддерживаемые варианты: macOS Intel/Apple Silicon, Linux x86_64/ARM64 с glibc, Windows x64. См. docs/PORTABILITY.md.')
    if platform.system()=='Linux' and platform.libc_ver()[0]!='glibc':
        raise RuntimeError('Нативный комплект Linux рассчитан на glibc, не musl/Alpine. Используйте Docker-вариант.')
    wheels=validate_wheels(ROOT/'vendor/wheels',key)
    env=Path(directory).resolve()
    python=env_python(env)
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(env)
    else:
        try:
            check=subprocess.run([str(python),'-c','import sys; assert sys.version_info[:2]==(3,11)'],capture_output=True)
        except OSError as exc:
            raise RuntimeError('Существующая .venv не запускается на этой машине. Переименуйте её и повторите запуск.') from exc
        if check.returncode:
            raise RuntimeError('Существующая .venv использует другой Python. Переименуйте её и повторите запуск.')
    subprocess.run([str(python),'-m','pip','install','--no-index','--disable-pip-version-check',
                    '--find-links',str(wheels),'-r',str(ROOT/'requirements.txt')],check=True)
    return python


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--venv',default=str(ROOT/'.venv'))
    args=parser.parse_args()
    try:
        print(setup(args.venv))
    except (RuntimeError,OSError,subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc))
