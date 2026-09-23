# Офлайн-комплект

В `vendor/wheels/` включены все восемь закреплённых зависимостей и транзитивных пакетов для CPython 3.11 под macOS 12+ arm64/x86-64, Linux x86-64/ARM64 manylinux2014 и Windows amd64. Python должен быть установлен заранее. `manifest.json` содержит SHA-256 каждого wheel; setup_env.py проверяет комплект перед установкой.

Проверка установки в новое окружение без использования PyPI:

```bash
python3 scripts/setup_env.py --venv /tmp/aml-clean
/tmp/aml-clean/bin/python run_pipeline.py --out /tmp/aml-clean-output
```

Инсталлятор передаёт `--no-index --find-links` и не обращается к сети. `run.sh` использует его, только если нужные версии отсутствуют. В Windows `run.bat` вызывает `py -3.11` для первоначальной установки.

## Подготовка пакетов для другой платформы

На машине с интернетом и нужным Python:

```bash
python -m pip download --only-binary=:all: --dest wheelhouse -r requirements.txt
```

Перенесите wheelhouse, requirements.txt, исходники и data на целевую машину; установите:

```bash
python -m venv .venv
.venv/bin/python -m pip install --no-index --find-links wheelhouse -r requirements.txt
.venv/bin/python run_pipeline.py
```

Для Windows путь `.venv\Scripts\python.exe`. Комплект не рассчитан на Alpine/musl, Linux ARMv7, native Windows ARM или другие версии Python; для них требуется подготовить соответствующие колёса. При отсутствии бинарного пакета нужно отдельно подготовить поддерживаемое окружение, а не обещать офлайн-сборку из исходников.

## Пересборка включённого набора

Команда для одной платформы (заменить platform/dest для остальных):

```bash
python -m pip download --only-binary=:all: --python-version 311 --implementation cp --abi cp311 --platform manylinux2014_x86_64 --dest vendor/wheels/linux-x86_64-py311 -r requirements.txt
```

Для macOS: `macosx_12_0_arm64` или `macosx_12_0_x86_64`, для Linux ARM64: `manylinux2014_aarch64`, для Windows: `win_amd64`. После изменения пакетов заново создайте манифест:

```bash
python scripts/wheel_manifest.py
```

Колёса занимают около 320 MB; это установочные зависимости, а не внешние данные клиентов. Не удаляйте их из сдаваемого офлайн-комплекта. Пакеты содержат собственные лицензии в dist-info.
