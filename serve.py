#!/usr/bin/env python3
"""Локальная пересборка и просмотр. Обновление не стирает несохранённый комментарий."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit
from aml_assistant.service import AssistantService

ROOT = Path(__file__).resolve().parent
STATE = {'revision':0,'error':None,'building':False}
ASSISTANT = None
RELOAD = '''<script>
let revision=null;
setInterval(async()=>{try{const s=await(await fetch('/__state',{cache:'no-store'})).json();
if(s.error){document.title='Ошибка пересборки — AML';return}
if(revision===null){revision=s.revision;return}
if(s.revision!==revision && !s.building && !(typeof caseDirty!=='undefined' && caseDirty) && !(typeof assistantBusy!=='undefined' && assistantBusy)){location.reload()}
}catch(e){}},1500);
</script>'''.encode('utf-8')


def rebuild():
    STATE['building']=True
    try:
        subprocess.run([sys.executable,str(ROOT/'run_pipeline.py')],cwd=ROOT,check=True)
        STATE['revision']+=1
        STATE['error']=None
    except subprocess.CalledProcessError as exc:
        STATE['error']=str(exc)
    finally:
        STATE['building']=False


def stamp():
    files=[ROOT/'run_pipeline.py']
    for folder in ('pipeline','app','data'):
        files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    return [(str(p),p.stat().st_mtime_ns,p.stat().st_size) for p in sorted(files)]


def watch():
    previous=stamp()
    while True:
        time.sleep(1)
        current=stamp()
        if current!=previous:
            rebuild()
            previous=current


class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(ROOT/'output'),**kwargs)

    def end_headers(self):
        self.send_header('Cache-Control','no-store, max-age=0')
        super().end_headers()

    def do_GET(self):
        path=self.path.split('?',1)[0]
        if path == '/api/assistant/status':
            return self.send_json(200, ASSISTANT.status() if ASSISTANT else {'available':False, 'reason':'LLM не запущен.'})
        elif path=='/__state':
            body=json.dumps(STATE).encode()
            mime='application/json'
        elif path in ('/','/graph.html','/output/graph.html'):
            body=(ROOT/'output/graph.html').read_bytes().replace(b'</html>',RELOAD+b'</html>')
            mime='text/html; charset=utf-8'
        else:
            return super().do_GET()
        self.send_response(200)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        if self.path != '/api/assistant/ask':
            return self.send_json(404, {'error':'Маршрут не найден.'})
        host = self.headers.get('Host', '')
        origin = self.headers.get('Origin')
        try:
            local = urlsplit('http://' + host).hostname in ('127.0.0.1', 'localhost', '::1')
        except ValueError:
            local = False
        if (not local or (origin and origin != 'http://' + host)
                or self.headers.get('X-AML-Request') != '1'
                or self.headers.get_content_type() != 'application/json'):
            return self.send_json(403, {'error':'Разрешены только локальные запросы из интерфейса проекта.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16000:
                return self.send_json(413, {'error':'Запрос слишком большой или пустой.'})
            body = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            return self.send_json(400, {'error':'Некорректный JSON.'})
        if STATE['building']:
            return self.send_json(409, {'error':'Идёт пересчёт графа. Повторите запрос после завершения.'})
        if ASSISTANT is None:
            return self.send_json(503, {'error':'Помощник не инициализирован.'})
        status, result = ASSISTANT.ask(body)
        self.send_json(status, result)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--host',default='127.0.0.1',help='В Docker: 0.0.0.0; нативно по умолчанию только localhost')
    args=parser.parse_args()
    try:
        server=ThreadingHTTPServer((args.host,args.port),Handler)
    except OSError as exc:
        raise SystemExit(f'Порт {args.port} занят или недоступен: {exc}. Остановите прежний сервер либо используйте --port 8766.')
    rebuild()
    if STATE['error']:
        raise SystemExit(STATE['error'])
    ASSISTANT = AssistantService(ROOT)
    if ASSISTANT.runtime.info['installed']:
        print('Загрузка локального LLM на CPU…', flush=True)
        ASSISTANT.runtime.start()
    print(json.dumps(ASSISTANT.runtime.status(), ensure_ascii=False), flush=True)
    threading.Thread(target=watch,daemon=True).start()
    print(f'Открыть http://127.0.0.1:{args.port}/graph.html — пересборка и обновление включены',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        ASSISTANT.runtime.stop()
