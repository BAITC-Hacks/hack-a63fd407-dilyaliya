"""Graph queries and evidence are computed in Python, never invented by the LLM."""
import json
from pathlib import Path


class ToolError(ValueError):
    pass


def money(value):
    return f'{value:,.2f} KZT'


class GraphTools:
    def __init__(self, snapshot):
        self.data = snapshot
        self.nodes = {n['gid']: n for n in snapshot['nodes']}
        self.edges = snapshot['edges']
        self.clusters = {c['cluster_id']: c for c in snapshot['clusters']}
        self.facts = {}

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text(encoding='utf-8')))

    def gids(self, values, minimum=1, maximum=5):
        if not isinstance(values, list) or not minimum <= len(values) <= maximum:
            raise ToolError(f'Нужно от {minimum} до {maximum} gid строками.')
        if any(not isinstance(g, str) or g not in self.nodes for g in values):
            raise ToolError('Неизвестный gid. Используйте только строки из запроса или результата инструмента.')
        unique = list(dict.fromkeys(values))
        if len(unique) < minimum:
            raise ToolError(f'Нужно минимум {minimum} разных gid.')
        return unique

    def fact(self, text, gids=(), values=None):
        ref = f'E{len(self.facts)+1}'
        item = {'ref': ref, 'text': text, 'gids': list(dict.fromkeys(gids)), 'values': values or {}}
        self.facts[ref] = item
        return item

    def node_fact(self, gid):
        n = self.nodes[gid]
        contributions = {k.removeprefix('priority_'): v for k, v in n.items()
                         if k.startswith('priority_') and k != 'priority_score'}
        return self.fact(
            f'gid {gid}. {n["evidence"]}. Приоритет {n["priority_score"]:.4f}; '
            f'вход {money(n["sum_in"])}; выход {money(n["sum_out"])}. '
            f'Правило: {n["rule_text"]}.', [gid],
            {'role': n['role'], 'role_score': n['role_score'], 'cluster_id': n['cluster_id'],
             'priority_score': n['priority_score'], 'contributions': contributions,
             'fan_in': n['fan_in'], 'fan_out': n['fan_out'],
             'sum_in': n['sum_in'], 'sum_out': n['sum_out'],
             'fifo_strict_share': n['fifo_strict_share'],
             'fifo_same_day_possible_share': n['fifo_same_day_possible_share'],
             'is_seed': n['is_seed'], 'is_depth4_leaf': n['is_depth4_leaf']})

    def call(self, action):
        if not isinstance(action, dict) or action.get('action') not in CATALOG:
            raise ToolError('Неизвестный инструмент.')
        name = action['action']
        allowed = set(CATALOG[name]['properties']) | {'action'}
        if set(action) - allowed:
            raise ToolError('Неизвестные аргументы инструмента.')
        required = set(CATALOG[name]['required'])
        if not required <= set(action):
            raise ToolError('Не хватает обязательных аргументов.')
        limit = action.get('limit', 5)
        if type(limit) is not int or not 1 <= limit <= 10:
            raise ToolError('limit должен быть целым числом от 1 до 10.')
        if name == 'top_nodes':
            role = action.get('role', 'all')
            if role not in ROLES + ['all']:
                raise ToolError('Неизвестная роль.')
            rows = [n for n in self.nodes.values() if role == 'all' or n['role'] == role]
            rows.sort(key=lambda n: (-n['priority_score'], int(n['gid'])))
            return [self.node_fact(n['gid']) for n in rows[:limit]] or [self.fact('Узлов с такой ролью в выборке нет.')]
        if name == 'node_details':
            return [self.node_fact(g) for g in self.gids(action['gids'])]
        if name == 'shared_recipients':
            senders = self.gids(action['gids'], minimum=2, maximum=10)
            destinations = [{e['dst'] for e in self.edges if e['src'] == g} for g in senders]
            shared = set.intersection(*destinations)
            rows = []
            for gid in shared:
                transfers = [e for e in self.edges if e['src'] in senders and e['dst'] == gid]
                rows.append((sum(e['sum_kzt'] for e in transfers), gid, transfers))
            rows.sort(key=lambda r: (-r[0], int(r[1])))
            facts = [self.fact(f'Общих прямых получателей у выбранных {len(senders)} отправителей: {len(shared)}. '
                               'Проверяются исходящие рёбра всех выбранных отправителей.', senders,
                               {'total': len(shared), 'senders': senders})]
            for total, gid, transfers in rows[:limit]:
                facts.append(self.fact(f'gid {gid} получил от каждого из {len(senders)} выбранных отправителей; '
                                       f'сумма по этим связям {money(total)}. Это структура переводов, не вывод о виновности.',
                                       [gid, *senders], {'recipient': gid, 'sum_kzt': total, 'edges': transfers}))
            return facts
        if name == 'neighbors':
            gid = self.gids([action['gid']])[0]
            direction = action['direction']
            if direction not in ('in', 'out', 'both'):
                raise ToolError('direction: in, out или both.')
            rows = [e for e in self.edges if (direction in ('out', 'both') and e['src'] == gid)
                    or (direction in ('in', 'both') and e['dst'] == gid)]
            rows.sort(key=lambda e: (-e['sum_kzt'], int(e['src']), int(e['dst'])))
            return [self.fact(f'{e["src"]} → {e["dst"]}: {money(e["sum_kzt"])}; {e["n_tx"]} операций за месяц.',
                              [e['src'], e['dst']], e) for e in rows[:limit]] or [self.fact('Связей в выбранном направлении нет.', [gid])]
        if name == 'seed_paths':
            gid = self.gids([action['gid']])[0]
            paths = self.data['cases'][gid]['paths']
            paths = sorted(paths, key=lambda p: (len(p['gids']), int(p['seed'])))
            return [self.fact('Направленный путь от seed: ' + ' → '.join(p['gids']) +
                              '. Наличие рёбер не доказывает хронологию и движение одной суммы.',
                              p['gids'], {'path': p['gids']}) for p in paths[:limit]] or [self.fact('Путь от seed в наблюдаемом графе не найден.', [gid])]
        if name == 'missing_data':
            facts = []
            for gid in self.gids(action['gids'], maximum=3):
                requests = self.data['cases'][gid]['requests']
                facts.append(self.fact(f'gid {gid}. ' + ' '.join(r['reason'] + ' ' + r['request'] for r in requests),
                                       [gid], {'requests': requests}))
            return facts
        if name == 'cluster_summary':
            cid = action['cluster_id']
            if type(cid) is not int or cid not in self.clusters:
                raise ToolError('Неизвестный cluster_id.')
            c = self.clusters[cid]
            gids = [str(g) for g in json.loads(c['top_gids'])]
            return [self.fact(f'Кластер {cid}: {c["n_nodes"]} узлов, {c["n_seed"]} seed. {c["hypothesis"]}', gids, c)]
        if name == 'patterns':
            kind = action['kind']
            gid = action.get('gid', '')
            if gid:
                self.gids([gid])
            if kind == 'anomalies':
                rows = [n for n in self.nodes.values() if (not gid or n['gid'] == gid)
                        and any(n[k] for k in ('burst_flag', 'synchronized_in_flag', 'repeated_amount_flag', 'depth_outlier_flag'))]
                rows.sort(key=lambda n: (-n['priority_score'], int(n['gid'])))
                return [self.fact(f'gid {n["gid"]}: {n["anomaly_evidence"]}. Это сигналы для проверки.',
                                  [n['gid']]) for n in rows[:limit]] or [self.fact('Таких сигналов не выявлено.', [gid] if gid else [])]
            if kind not in ('cycles', 'repeated_routes'):
                raise ToolError('Неизвестный вид паттерна.')
            rows = [r for r in self.data['analytics']['patterns'][kind] if not gid or gid in r['gids']]
            return [self.fact(('Цикл: ' if kind == 'cycles' else 'Повторный FIFO-маршрут: ') +
                              ' → '.join(r['gids']) + '. ' + r['evidence'], r['gids'], r)
                    for r in rows[:limit]] or [self.fact('Таких паттернов не найдено.', [gid] if gid else [])]
        raise ToolError('Неизвестный инструмент.')


ROLES = ['coordinator', 'consolidator', 'distributor', 'transit', 'terminal', 'peripheral']
GID = {'type': 'string'}
GIDS = {'type': 'array', 'items': GID, 'minItems': 1, 'maxItems': 10}
LIMIT = {'type': 'integer', 'minimum': 1, 'maximum': 10}
CATALOG = {
    'top_nodes': {'description': 'Ranked priorities, optionally restricted by role.',
                  'properties': {'role': {'type': 'string', 'enum': ['all', *ROLES]}, 'limit': LIMIT}, 'required': ['role', 'limit']},
    'node_details': {'description': 'Explain or compare roles, metrics and score contributions of specified nodes.',
                     'properties': {'gids': GIDS}, 'required': ['gids']},
    'shared_recipients': {'description': 'Find recipients receiving directly from EVERY supplied sender, with exact sums.',
                          'properties': {'gids': GIDS, 'limit': LIMIT}, 'required': ['gids', 'limit']},
    'neighbors': {'description': 'Incoming payers or outgoing recipients with directed edges and sums.',
                  'properties': {'gid': GID, 'direction': {'type': 'string', 'enum': ['in', 'out', 'both']}, 'limit': LIMIT},
                  'required': ['gid', 'direction', 'limit']},
    'seed_paths': {'description': 'Shortest directed paths from seeds to a node. Does not establish chronological provenance.',
                   'properties': {'gid': GID, 'limit': LIMIT}, 'required': ['gid', 'limit']},
    'cluster_summary': {'description': 'Size, seeds, amounts and hypothesis for one community.',
                        'properties': {'cluster_id': {'type': 'integer', 'minimum': 0}}, 'required': ['cluster_id']},
    'missing_data': {'description': 'Specific missing data and next requests for up to three nodes.',
                     'properties': {'gids': GIDS}, 'required': ['gids']},
    'patterns': {'description': 'Cycles, repeated FIFO routes or anomaly signals; optional gid filter.',
                 'properties': {'kind': {'type': 'string', 'enum': ['cycles', 'repeated_routes', 'anomalies']},
                                'gid': GID, 'limit': LIMIT}, 'required': ['kind', 'gid', 'limit']},
}


def action_schema(refs=(), allowed_gids=None, allowed_tools=None, allow_finish=True):
    """Constrain long identifiers to observed strings, never floating-point numbers."""
    variants = []
    if refs and allow_finish:
        variants.append({'type': 'object', 'properties': {'action': {'const': 'finish'},
                         'refs': {'type': 'array', 'items': {'type': 'string', 'enum': list(refs)}, 'minItems': 1, 'maxItems': 32}},
                         'required': ['action', 'refs'], 'additionalProperties': False})
    variants.append({'type': 'object', 'properties': {'action': {'const': 'clarify'},
                     'reason': {'type': 'string', 'enum': ['select_node', 'select_senders', 'outside_dataset', 'rephrase']}},
                     'required': ['action', 'reason'], 'additionalProperties': False})
    for name, tool in CATALOG.items():
        if allowed_tools is not None and name not in allowed_tools:
            continue
        properties = json.loads(json.dumps(tool['properties']))
        if allowed_gids is not None:
            known = sorted(set(allowed_gids))
            if not known and name in ('node_details', 'shared_recipients', 'neighbors', 'seed_paths', 'missing_data'):
                continue
            if 'gids' in properties:
                properties['gids']['items'] = {'type': 'string', 'enum': known}
            if 'gid' in properties:
                properties['gid'] = {'type': 'string', 'enum': known + ([''] if name == 'patterns' else [])}
        if 'gids' in properties:
            properties['gids']['maxItems'] = {'node_details': 5, 'missing_data': 3}.get(name, 10)
            properties['gids']['minItems'] = 2 if name == 'shared_recipients' else 1
        variants.append({'type': 'object', 'properties': {'action': {'const': name}, **properties},
                         'required': ['action', *tool['required']], 'additionalProperties': False})
    return {'oneOf': variants}


def plan_schema():
    return {'type': 'object', 'properties': {
        'tasks': {'type': 'array', 'items': {'type': 'string', 'enum': list(CATALOG)}, 'maxItems': 3},
        'clarify_reason': {'type': 'string', 'enum': ['none', 'select_node', 'select_senders', 'outside_dataset', 'rephrase']}},
        'required': ['tasks', 'clarify_reason'], 'additionalProperties': False}
