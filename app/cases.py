"""Проверяемый контекст дела без внешних данных и обвинительных выводов."""
from collections import deque


def missing_data(node):
    requests = []
    def add(reason, request):
        requests.append({'reason': reason, 'request': request})
    if node['is_depth4_leaf']:
        add('Глубина 4, исходящих связей не видно: обход здесь завершён.',
            'Запросить дальнейшие исходящие переводы и расширить обход за четвёртое колено.')
    if node['is_seed'] or node['zero_sum_in'] or (node['pass_through_ratio'] or 0) > 1.2:
        add('Вход seed неполон либо вход отсутствует/меньше выхода; баланс не восстановлен.',
            'Запросить полный входящий поток и остаток на начало периода; сверить источники средств.')
    if node['sum_in'] > 0 and node['sum_out'] > 0:
        add('Есть вход и выход, но даты в этой выгрузке имеют дневную точность.',
            'Запросить точное время и часовой пояс операций, проверить порядок входов и выходов.')
    if node['sum_in'] > node['sum_out']:
        add('Наблюдаемый вход превышает выход; это не доказывает оседание средств.',
            'При разрешённом доступе проверить межбанковские переводы, снятия наличных и другие способы вывода.')
    if node['fan_in'] == 0 and node['fan_out'] == 0:
        add('Узел есть в списке, но операций в выборке нет.',
            'Проверить полноту выгрузки и наличие операций за пределами её фильтров.')
    add('Выборка ограничена июлем 2026, одним банком и суммами от 5000 KZT.',
        'Запросить согласованное расширение периода и операции ниже 5000 KZT; проверить полноту охвата каналов.')
    return requests


def case_context(records, graph):
    # Одна кратчайшая направленная цепочка от каждого достижимого seed.
    paths = {str(gid): [] for gid in graph}
    for seed in sorted(r['gid'] for r in records if r['is_seed']):
        parent = {seed: None}
        queue = deque([seed])
        while queue:
            src = queue.popleft()
            for dst in sorted(graph.successors(src)):
                if dst not in parent:
                    parent[dst] = src
                    queue.append(dst)
        for target in parent:
            path, cursor = [], target
            while cursor is not None:
                path.append(str(cursor))
                cursor = parent[cursor]
            paths[str(target)].append({'seed': str(seed), 'gids': path[::-1]})
    return {str(r['gid']): {'paths': paths[str(r['gid'])], 'requests': missing_data(r)} for r in records}
