FROM python:3.11-slim-bookworm AS dependencies
WORKDIR /build
COPY requirements.txt ./
COPY scripts/setup_env.py scripts/setup_env.py
COPY vendor/wheels/manifest.json vendor/wheels/manifest.json
COPY vendor/wheels/linux-x86_64-py311/ vendor/wheels/linux-x86_64-py311/
COPY vendor/wheels/linux-aarch64-py311/ vendor/wheels/linux-aarch64-py311/
RUN python scripts/setup_env.py --venv /opt/venv

FROM python:3.11-slim-bookworm
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY --from=dependencies /opt/venv /opt/venv
COPY pipeline/ pipeline/
COPY app/ app/
COPY aml_assistant/ aml_assistant/
COPY scripts/setup_llm.py scripts/llm_assets.json scripts/
COPY data/ data/
COPY run_pipeline.py serve.py ./
RUN groupadd --gid 10001 aml && useradd --uid 10001 --gid 10001 --no-create-home aml && mkdir output && chown aml:aml output
USER aml
EXPOSE 8765
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s CMD python -c "import json,urllib.request; s=json.load(urllib.request.urlopen('http://127.0.0.1:8765/__state',timeout=2)); assert not s['error']"
CMD ["python", "serve.py", "--host", "0.0.0.0", "--port", "8765"]
