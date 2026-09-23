"""HTTP-facing agent service with an immutable graph snapshot per request."""
import json
from pathlib import Path
import threading
from .agent import investigate
from .runtime import LocalRuntime


class AssistantService:
    def __init__(self, root, runtime=None):
        self.root = Path(root)
        self.runtime = runtime or LocalRuntime(root)
        self.busy = threading.Lock()

    def snapshot(self):
        path = self.root / 'output/assistant_data.json'
        return json.loads(path.read_text(encoding='utf-8'))

    def status(self):
        result = self.runtime.status()
        result['busy'] = self.busy.locked()
        try:
            result['dataset_sha256'] = self.snapshot()['fingerprint']
        except (OSError, ValueError, KeyError):
            result['available'] = False
            result['reason'] = 'Пересчитайте граф: не найден снимок данных помощника.'
        return result

    def ask(self, body):
        if not isinstance(body, dict) or set(body) - {'question', 'selected_gid', 'dataset_sha256', 'analysis_sha256'}:
            return 400, {'error': 'Некорректный запрос.'}
        if not self.busy.acquire(blocking=False):
            return 429, {'error': 'Помощник уже выполняет запрос. Дождитесь завершения.'}
        try:
            snapshot = self.snapshot()
            if (body.get('dataset_sha256') != snapshot['fingerprint']
                    or body.get('analysis_sha256') != snapshot['analysis_sha256']):
                return 409, {'error': 'Данные страницы изменились. Обновите страницу перед запросом.'}
            if not self.runtime.status()['available']:
                return 503, {'error': self.runtime.status().get('reason') or 'LLM недоступен. Перезапустите сервер после установки модели.'}
            result = investigate(snapshot, self.runtime, body.get('question'), body.get('selected_gid'))
            result['model'] = self.runtime.info.get('model')
            result['engine'] = self.runtime.info.get('engine_version')
            result['execution'] = 'local_cpu'
            return 200, result
        except (ValueError, TypeError) as exc:
            return 400, {'error': str(exc)}
        except (OSError, KeyError) as exc:
            return 503, {'error': 'Снимок данных недоступен или неполон. Повторите пересчёт.'}
        finally:
            self.busy.release()
