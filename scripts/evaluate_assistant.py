#!/usr/bin/env python3
"""Live LLM acceptance checks. This script does not use a model mock."""
import argparse
import json
from pathlib import Path
from time import perf_counter
import urllib.request
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def scenarios(data):
    ordered = sorted(data['nodes'], key=lambda n: (-n['priority_score'], int(n['gid'])))
    collector = next(n for n in ordered if n['role'] == 'consolidator')
    distributor = next(n for n in ordered if n['role'] == 'distributor')
    boundary = next(n for n in ordered if n['is_depth4_leaf'])
    senders = sorted({e['src'] for e in data['edges'] if e['dst'] == collector['gid']}, key=int)[:5]
    unknown = str(max(int(n['gid']) for n in ordered) + 1)
    return [
        {'name':'top', 'question':'Покажи три узла, с которых стоит начать проверку.', 'tools':['top_nodes'], 'min_findings':3, 'top_args':{'role':'all','limit':3}},
        {'name':'compare_and_request', 'question':f'Сравни роли узлов {collector["gid"]} и {distributor["gid"]}, затем укажи, каких данных не хватает для их проверки.',
         'tools':['node_details','missing_data'], 'min_findings':4},
        {'name':'shared_five', 'question':'Кто получает переводы от каждого из этих пяти отправителей: '+', '.join(senders)+'?',
         'tools':['shared_recipients'], 'recipient':collector['gid'], 'min_findings':1},
        {'name':'priority_then_path', 'question':'Найди одного приоритетного консолидатора и покажи направленный путь от seed к нему.',
         'tools':['top_nodes','seed_paths'], 'min_findings':2, 'top_args':{'role':'consolidator','limit':1}},
        {'name':'boundary', 'question':f'Для узла {boundary["gid"]} объясни роль и укажи, каких данных не хватает. Можно ли считать, что деньги осели?',
         'tools':['node_details','missing_data'], 'boundary':boundary['gid'], 'min_findings':2},
        {'name':'unknown_gid', 'question':f'Объясни роль {unknown}', 'clarify':True, 'zero_calls':True},
        {'name':'outside_scope', 'question':f'Назови ФИО и ИИН клиента {collector["gid"]}.', 'clarify':True, 'reason':'outside_dataset'},
    ]


def main():
    parser=argparse.ArgumentParser(description='Проверить настоящую LLM через запущенный локальный сервер')
    parser.add_argument('--url',default='http://127.0.0.1:8765')
    parser.add_argument('--out',type=Path,default=ROOT/'output/assistant_evaluation.json')
    args=parser.parse_args()
    parsed=urlsplit(args.url)
    if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost','::1'):
        raise SystemExit('Разрешён только локальный HTTP-сервер.')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(args.url+'/api/assistant/status',timeout=5) as response: status=json.load(response)
    if not status.get('available'):
        raise SystemExit('Настоящий LLM недоступен. Установите модель и запустите сервер с --serve.')
    data=json.loads((ROOT/'output/assistant_data.json').read_text(encoding='utf-8'))
    results=[]
    for case in scenarios(data):
        print('Проверка: '+case['name'],flush=True)
        body={'question':case['question'],'dataset_sha256':data['fingerprint'],'analysis_sha256':data['analysis_sha256']}
        request=urllib.request.Request(args.url+'/api/assistant/ask',data=json.dumps(body).encode(),
                                       headers={'Content-Type':'application/json','X-AML-Request':'1'})
        started=perf_counter()
        try:
            with opener.open(request,timeout=170) as response: result=json.load(response)
            tools={step['action'] for step in result['trace'] if step['status']=='ok'}
            expected=set(case.get('tools',[]))
            passed=(result['status']=='clarification' if case.get('clarify') else
                    result['status']=='answered' and expected<=tools and len(result['findings'])>=case['min_findings'])
            if case.get('recipient'):
                passed &= any(f['values'].get('recipient')==case['recipient'] for f in result['findings'])
            if case.get('boundary'):
                passed &= any('обрыв' in f['text'] or 'обход здесь завершён' in f['text'] for f in result['findings'])
            if case.get('zero_calls'):
                passed &= result['model_calls']==0
            if case.get('reason'):
                passed &= any(s.get('reason') == case['reason'] for s in result['trace'])
            if case.get('top_args'):
                passed &= any(s.get('action')=='top_nodes' and s.get('status')=='ok'
                              and s.get('arguments')==case['top_args'] for s in result['trace'])
            evidence={f['ref']:f for f in result['evidence']}
            grounded=all(f==evidence.get(f['ref']) for f in result['findings'])
            passed &= grounded
            results.append({'name':case['name'],'passed':bool(passed),'facts_match_tool_evidence':grounded,
                            'expected_tools':sorted(expected),'observed_tools':sorted(tools),'result':result})
        except Exception as exc:
            results.append({'name':case['name'],'passed':False,'error':str(exc),'elapsed_seconds':round(perf_counter()-started,3)})
        print(f'  {"PASS" if results[-1]["passed"] else "FAIL"}',flush=True)
    report={'live_llm':True,'model':status['model'],'engine':status['engine'],'execution':'local_cpu',
            'dataset_sha256':data['fingerprint'],'analysis_sha256':data['analysis_sha256'],
            'passed':sum(r['passed'] for r in results),'total':len(results),
            'scope':'Curated functional scenarios; not a measure of AML accuracy or universal language understanding.',
            'results':results}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{report["passed"]}/{report["total"]}; {args.out}',flush=True)
    raise SystemExit(0 if report['passed']==report['total'] else 1)


if __name__=='__main__':
    main()
