#!/usr/bin/env python3
"""Единая точка запуска: только стандартная библиотека до установки зависимостей."""
import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path
from scripts.setup_env import env_python, platform_key, setup

ROOT=Path(__file__).resolve().parent


def environment_ready(python):
    try:
        return subprocess.run([str(python),str(ROOT/'scripts/check_environment.py')],
                              stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
    except OSError:
        return False


def main(argv=None):
    parser=argparse.ArgumentParser(description='AML: кроссплатформенный офлайн-запуск')
    parser.add_argument('--serve',action='store_true',help='Пересобрать и запустить сайт с автообновлением')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--doctor',action='store_true',help='Диагностика без установки и изменения файлов')
    parser.add_argument('--data',type=Path)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--top',type=int,default=30)
    args=parser.parse_args(argv)
    python=env_python(ROOT/'.venv')
    if args.doctor:
        print(json.dumps({'os':platform.system(),'architecture':platform.machine(),
                          'launcher_python':platform.python_version(),'wheel_set':platform_key(),
                          'environment_ready':environment_ready(python),
                          'inputs_present':all((ROOT/'data'/name).exists() for name in ('nodes.parquet','edges.parquet','transactions.parquet'))},ensure_ascii=False,indent=2))
        return 0
    if args.serve and (args.data or args.out or args.top!=30):
        parser.error('--serve использует data/ и output/ с top30; --data/--out/--top предназначены для пакетного запуска')
    if not environment_ready(python):
        python=setup(ROOT/'.venv')
    command=[str(python),str(ROOT/('serve.py' if args.serve else 'run_pipeline.py'))]
    if args.serve:
        command+=['--port',str(args.port)]
    else:
        for name,value in (('--data',args.data),('--out',args.out)):
            if value is not None:
                command += [name,str(value.resolve())]
        command+=['--top',str(args.top)]
    return subprocess.call(command,cwd=ROOT)


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except (RuntimeError,OSError,subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc))
