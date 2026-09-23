#!/usr/bin/env python3
"""Explicit one-time download; normal application startup never downloads weights."""
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import shutil
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = json.loads(Path(__file__).with_name('llm_assets.json').read_text(encoding='utf-8'))


def platform_key(system=None, machine=None):
    cpu = (machine or platform.machine()).lower()
    cpu = {'aarch64': 'arm64', 'amd64': 'x86_64'}.get(cpu, cpu)
    return f'{system or platform.system()}-{cpu}'


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(8 * 1024**2), b''):
            digest.update(block)
    return digest.hexdigest()


def download(url, destination, expected):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and sha256(destination) == expected:
        print(f'Проверен: {destination.name}', flush=True)
        return
    temporary = destination.with_suffix(destination.suffix + '.part')
    print(f'Скачивание {destination.name}', flush=True)
    request = urllib.request.Request(url, headers={'User-Agent': 'HackAlem-local-LLM-setup/1'})
    with urllib.request.urlopen(request, timeout=60) as source, temporary.open('wb') as out:
        count = 0
        while block := source.read(4 * 1024**2):
            out.write(block)
            count += len(block)
            if count // (128 * 1024**2) != (count - len(block)) // (128 * 1024**2):
                print(f'  {count / 1024**2:.0f} MiB', flush=True)
    if sha256(temporary) != expected:
        raise RuntimeError(f'SHA-256 не совпал: {destination.name}. Файл не используется.')
    temporary.replace(destination)


def unpack(archive, destination):
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    if archive.suffix == '.zip':
        with zipfile.ZipFile(archive) as source:
            for entry in source.infolist():
                if not (root / entry.filename).resolve().is_relative_to(root):
                    raise RuntimeError('Небезопасный путь в архиве.')
                if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise RuntimeError('Symlink в ZIP не поддерживается.')
            source.extractall(root)
    else:
        with tarfile.open(archive) as source:
            for entry in source.getmembers():
                target = (root / entry.name).resolve()
                if not target.is_relative_to(root) or entry.isdev():
                    raise RuntimeError('Небезопасный путь в архиве.')
                if entry.issym() or entry.islnk():
                    link = (target.parent if entry.issym() else root) / entry.linkname
                    if not link.resolve().is_relative_to(root):
                        raise RuntimeError('Небезопасная ссылка в архиве.')
            if hasattr(tarfile, 'data_filter'):
                source.extractall(root, filter='data')
            else:
                source.extractall(root)


def check(root=ROOT):
    directory = Path(root) / '.local_ai'
    path = directory / 'installed.json'
    if not path.exists():
        return {'installed': False, 'reason': 'Модель не установлена. Запустите scripts/setup_llm.py --download.'}
    try:
        info = json.loads(path.read_text(encoding='utf-8'))
        required = {'platform', 'model', 'model_path', 'model_sha256', 'server_path', 'runtime_sha256', 'engine_version'}
        if not isinstance(info, dict) or not required <= info.keys():
            raise ValueError('Incomplete manifest')
    except (OSError, ValueError):
        return {'installed': False, 'reason': 'Манифест LLM повреждён. Повторите scripts/setup_llm.py --download.'}
    if info.get('platform') != platform_key():
        return {'installed': False, 'reason': 'Движок скопирован с другой платформы; подготовьте его на этой ОС.'}
    for relative in ('model_path', 'server_path'):
        value = (directory / info[relative]).resolve()
        if not value.is_relative_to(directory.resolve()) or not value.is_file():
            return {'installed': False, 'reason': 'Комплект LLM неполон.'}
    return {'installed': True, **info}


def main():
    parser = argparse.ArgumentParser(description='Подготовить локальный CPU LLM; ~1,9 ГБ, один раз нужен интернет')
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not args.download:
        print(json.dumps(check(), ensure_ascii=False, indent=2))
        return
    key = platform_key()
    asset = ASSETS['engine_assets'].get(key)
    if asset is None:
        raise SystemExit(f'Нет закреплённой сборки для {key}.')
    directory = ROOT / '.local_ai'
    directory.mkdir(exist_ok=True)
    model = ASSETS['model']
    model_path = directory / 'models' / model['name']
    required = (0 if model_path.exists() else model['size']) + 250 * 1024**2
    if shutil.disk_usage(directory).free < required:
        raise SystemExit('Недостаточно места для модели и движка; нужно около 2,1 ГБ.')
    archive = directory / 'downloads' / asset['name']
    download(f'https://github.com/ggml-org/llama.cpp/releases/download/{ASSETS["engine_version"]}/{asset["name"]}',
             archive, asset['sha256'])
    engine = directory / 'runtime' / key
    unpack(archive, engine)
    name = 'llama-server.exe' if os.name == 'nt' else 'llama-server'
    servers = list(engine.rglob(name))
    if len(servers) != 1:
        raise RuntimeError('В архиве не найден единственный llama-server.')
    if os.name != 'nt':
        servers[0].chmod(servers[0].stat().st_mode | 0o111)
    download(f'https://huggingface.co/{model["repository"]}/resolve/{model["revision"]}/{model["name"]}',
             model_path, model['sha256'])
    info = {'platform': key, 'model': model['repository'], 'model_revision': model['revision'],
            'model_sha256': model['sha256'], 'engine_version': ASSETS['engine_version'],
            'model_path': model_path.relative_to(directory).as_posix(),
            'server_path': servers[0].relative_to(directory).as_posix(),
            'runtime_sha256': {p.relative_to(directory).as_posix(): sha256(p)
                               for p in engine.rglob('*') if p.is_file()}}
    (directory / 'installed.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
    print('Готово. Модель и движок проверены по SHA-256. Теперь запустите run.sh --serve или run.bat --serve.', flush=True)


if __name__ == '__main__':
    main()
