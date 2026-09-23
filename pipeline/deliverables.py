"""Демонстрационные примеры выбираются правилами из текущего результата."""
import json


def write_demo(df, destination):
    cases = []
    selectors = [('Консолидация', df.role.eq('consolidator')),
                 ('Веерная рассылка', df.role.eq('distributor')),
                 ('Граница наблюдения', df.is_depth4_leaf),
                 ('Транзитная гипотеза', df.role.eq('transit'))]
    for title, mask in selectors:
        selected = df[mask].sort_values(['priority_score','gid'],ascending=[False,True])
        if selected.empty:
            continue
        r = selected.iloc[0]
        cases.append({'title':title,'gid':str(r.gid),'role':r.role,'evidence':r.evidence,'rule':r.rule_text})
    text = ['# Демонстрация за 5 минут', '',
            '0:00–0:40 — запустить `sh run.sh`; показать время, 2248 узла, 3 CSV и контроль входов.',
            '0:40–1:10 — открыть graph.html, показать легенду, поиск, список приоритетов и схему решения.',
            '1:10–3:30 — разобрать первые три автоматически выбранных примера ниже.',
            '3:30–4:20 — показать циклы, аномалии, чувствительность порогов и удаление top-N против случайного удаления.',
            '4:20–5:00 — сохранить решение в карточке, выгрузить справку и запрос данных; назвать ограничения.', '']
    for c in cases:
        text += [f'## {c["title"]}: {c["gid"]}', c['evidence'], c['rule'],
                 'Найти gid → открыть карточку → показать операции и путь от seed → объяснить недостающие данные.', '']
    text += ['## Вопросы жюри',
             '- Почему не accuracy? Размеченных ролей нет; проверяем правила, сохранение сумм и устойчивость.',
             '- Почему 35 компонент? 16 содержат рёбра, 19 — изолированные seed, они сохранены.',
             '- Это AI? Основная аналитика — правила и графовые алгоритмы. Помощник распознаёт ограниченные запросы локально, без LLM.',
             '- Можно блокировать клиента? Нет: это список гипотез для ручной проверки.',
             '- Что означает FIFO? Сценарий распределения наблюдаемых сумм, а не доказательство происхождения денег.']
    (destination/'demo.md').write_text('\n\n'.join(text)+'\n',encoding='utf-8')
    (destination/'demo_cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
    return cases
