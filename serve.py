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

ROOT = Path(__file__).resolve().parent
STATE = {'revision':0,'error':None,'building':False}
RELOAD = '''<script>
let revision=null;
setInterval(async()=>{try{const s=await(await fetch('/__state',{cache:'no-store'})).json();
if(s.error){document.title='Ошибка пересборки — AML';return}
if(revision===null){revision=s.revision;return}
if(s.revision!==revision && !s.building && !(typeof caseDirty!=='undefined' && caseDirty)){location.reload()}
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
        if path=='/__state':
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
    threading.Thread(target=watch,daemon=True).start()
    print(f'Открыть http://127.0.0.1:{args.port}/graph.html — пересборка и обновление включены',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
