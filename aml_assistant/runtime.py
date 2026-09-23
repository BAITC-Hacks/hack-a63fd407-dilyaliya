"""Owned localhost llama.cpp process; CPU only, no network model downloads."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from scripts.setup_llm import ROOT, check, sha256


class ModelUnavailable(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ModelUnavailable('Перенаправление LLM-запроса запрещено.')


class LocalRuntime:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.process = None
        self.log = None
        self.port = None
        self.key = secrets.token_urlsafe(32)
        self.info = check(self.root)
        self.error = self.info.get('reason')
        self.ready = False
        self.lock = threading.Lock()

    def status(self):
        return {'available': self.ready and self.process is not None and self.process.poll() is None,
                'installed': self.info['installed'], 'model': self.info.get('model'),
                'engine': self.info.get('engine_version'), 'execution': 'local_cpu',
                'reason': self.error, 'max_steps': 6, 'network': 'localhost only'}

    def request(self, path, payload=None, timeout=45):
        if self.port is None:
            raise ModelUnavailable(self.error or 'LLM не запущен.')
        headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.key}
        request = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}',
                                         data=None if payload is None else json.dumps(payload).encode(), headers=headers)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        try:
            with opener.open(request, timeout=max(.1, timeout)) as response:
                raw = response.read(2 * 1024**2 + 1)
            if len(raw) > 2 * 1024**2:
                raise ModelUnavailable('LLM вернул слишком большой ответ.')
            return json.loads(raw)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise ModelUnavailable('Локальный LLM недоступен или превысил время ответа.') from exc

    def start(self):
        if not self.info['installed']:
            return False
        directory = self.root / '.local_ai'
        try:
            if sha256(directory / self.info['model_path']) != self.info['model_sha256']:
                raise ModelUnavailable('Модель повреждена; повторите setup_llm.py --download.')
            for relative, expected in self.info['runtime_sha256'].items():
                path = (directory / relative).resolve()
                if not path.is_relative_to(directory.resolve()) or sha256(path) != expected:
                    raise ModelUnavailable('Проверка контрольных сумм движка не пройдена.')
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                self.port = sock.getsockname()[1]
            log_dir = directory / 'logs'
            log_dir.mkdir(exist_ok=True)
            self.log = (log_dir / f'llama-{os.getpid()}.log').open('w', encoding='utf-8')
            executable = directory / self.info['server_path']
            if os.name != 'nt' and not os.access(executable, os.X_OK):
                # Some ZIP extractors discard Unix mode bits; bytes were verified above.
                executable.chmod(executable.stat().st_mode | 0o111)
            command = [str(executable), '-m', str(directory / self.info['model_path']),
                       '--host', '127.0.0.1', '--port', str(self.port), '--alias', 'aml-local',
                       '--api-key', self.key, '--n-gpu-layers', '0', '--device', 'none',
                       '--no-kv-offload', '--ctx-size', '8192', '--parallel', '1',
                       '--threads', str(min(6, max(1, (os.cpu_count() or 2)-1))), '--jinja', '--no-webui']
            env = dict(os.environ, CUDA_VISIBLE_DEVICES='-1')
            self.process = subprocess.Popen(command, stdout=self.log, stderr=subprocess.STDOUT, env=env)
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise ModelUnavailable(f'LLM не запустился. Диагностика: .local_ai/logs/llama-{os.getpid()}.log')
                try:
                    if self.request('/health', timeout=1).get('status') == 'ok':
                        self.ready, self.error = True, None
                        return True
                except ModelUnavailable:
                    pass
                time.sleep(.25)
            raise ModelUnavailable('Загрузка LLM заняла больше 60 секунд; проверьте свободную память.')
        except (OSError, KeyError, ModelUnavailable) as exc:
            self.error = str(exc)
            self.stop()
            return False

    def complete(self, messages, schema, timeout=45):
        if not self.status()['available']:
            raise ModelUnavailable(self.error or 'Локальный LLM не запущен.')
        result = self.request('/v1/chat/completions', {
            'model': 'aml-local', 'messages': messages, 'stream': False, 'temperature': 0,
            'seed': 42, 'max_tokens': 384, 'chat_template_kwargs': {'enable_thinking': False},
            'response_format': {'type': 'json_object', 'schema': schema}}, timeout=timeout)
        try:
            choice = result['choices'][0]
            if choice.get('finish_reason') == 'length':
                raise ValueError('truncated')
            action = json.loads(choice['message']['content'])
            if not isinstance(action, dict):
                raise ValueError('not an object')
            return action, result.get('usage', {})
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ModelUnavailable('Модель не вернула полное структурированное действие.') from exc

    def stop(self):
        self.ready = False
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self.log:
            self.log.close()
