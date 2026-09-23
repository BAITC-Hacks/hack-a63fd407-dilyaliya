"""Дополнительные сигналы, объяснимые относительно наблюдаемой выборки."""
import json
from itertools import islice
import networkx as nx
import numpy as np
import pandas as pd


def investigate(df, graph, tx, matches):
    df = df.copy()
    dated = tx.copy()
    dated['day'] = dated.date.dt.normalize()
    incoming = dated.groupby(['dst', 'day']).agg(payers=('src', 'nunique'), amount=('sum_kzt', 'sum'))
    events = pd.concat([dated[['src','day']].rename(columns={'src':'gid'}), dated[['dst','day']].rename(columns={'dst':'gid'})])
    daily = events.groupby(['gid','day']).size()
    df['peak_day_events'] = df.gid.map(daily.groupby(level=0).max()).fillna(0).astype(int)
    df['peak_day_share'] = (df.peak_day_events / (df.n_tx_in + df.n_tx_out).replace(0, np.nan)).fillna(0)
    df['max_same_day_payers'] = df.gid.map(incoming.payers.groupby(level=0).max()).fillna(0).astype(int)
    df['burst_flag'] = (df.peak_day_events >= 5) & (df.peak_day_share >= .5)
    df['synchronized_in_flag'] = df.max_same_day_payers >= 3
    repeat = dated.groupby(['src','dst','day','sum_kzt']).size().reset_index(name='n_tx')
    repeat = repeat[repeat.n_tx >= 3]
    repeated = set(repeat.src) | set(repeat.dst)
    df['repeated_amount_flag'] = df.gid.isin(repeated)
    df['depth_volume_p95'] = df.groupby('depth').volume.transform(lambda s: s.quantile(.95))
    df['depth_degree_p95'] = (df.fan_in+df.fan_out).groupby(df.depth).transform(lambda s: s.quantile(.95))
    group_size = df.groupby('depth').gid.transform('size')
    df['depth_outlier_flag'] = (group_size >= 20) & df.volume.gt(0) & (df.volume > df.depth_volume_p95) & ((df.fan_in+df.fan_out) > df.depth_degree_p95)
    names = [('burst_flag','всплеск ≥5 событий и ≥50% за день'),
             ('synchronized_in_flag','≥3 плательщиков за день'),
             ('repeated_amount_flag','≥3 одинаковых переводов по паре за день'),
             ('depth_outlier_flag','объём и степень выше P95 своего колена')]
    df['anomaly_evidence'] = ['; '.join(label for col,label in names if getattr(r,col)) or 'Дополнительных сигналов нет'
                              for r in df.itertuples(index=False)]
    cycles = []
    cycle_limit = 2000
    # Входной graph строится в фиксированном порядке; перечисление детерминировано.
    for component in sorted(nx.strongly_connected_components(graph), key=min):
        if len(component) < 2:
            continue
        for cycle in nx.simple_cycles(graph.subgraph(sorted(component)).copy(), length_bound=4):
            if len(cycle) < 2:
                continue
            k = cycle.index(min(cycle))
            cycle = cycle[k:] + cycle[:k]
            steps = [graph[a][b]['weight'] for a,b in zip(cycle, cycle[1:]+cycle[:1])]
            cycles.append({'gids': [str(g) for g in cycle], 'min_edge_kzt': min(steps),
                           'evidence': 'Цикл длиной 2–4 в месячном графе; возврат одной суммы и порядок дат не подтверждены.'})
            if len(cycles) > cycle_limit:
                break
        if len(cycles) > cycle_limit:
            break
    truncated = len(cycles) > cycle_limit
    cycles = sorted(cycles[:cycle_limit], key=lambda c: tuple(c['gids']))
    cycle_nodes = {int(g) for c in cycles for g in c['gids']}
    df['short_cycle_flag'] = df.gid.isin(cycle_nodes)
    rows = {f'row:{i+1}': r for i,r in enumerate(tx.itertuples(index=False))}
    route_events = []
    for r in matches[matches.scenario.eq('strict')].itertuples(index=False):
        a, c = rows[r.in_ref].src, rows[r.out_ref].dst
        if len({a, r.gid, c}) == 3:
            route_events.append(dict(src=a, via=r.gid, dst=c, in_ref=r.in_ref, out_ref=r.out_ref,
                                     matched_kzt=r.matched_kzt))
    routes = []
    if route_events:
        grouped = pd.DataFrame(route_events).groupby(['src','via','dst']).agg(
            n_in=('in_ref','nunique'), n_out=('out_ref','nunique'), matched_kzt=('matched_kzt','sum'))
        for (a,b,c),r in grouped[(grouped.n_in >= 2) & (grouped.n_out >= 2)].iterrows():
            routes.append({'gids':[str(a),str(b),str(c)], 'n_in':int(r.n_in), 'n_out':int(r.n_out),
                           'matched_kzt':float(r.matched_kzt),
                           'evidence':'Повторные FIFO-сопоставления за 1–2 дня; гипотеза маршрута, не трассировка идентичных денег.'})
    patterns = {'cycles':cycles, 'cycles_truncated':truncated, 'cycle_limit':cycle_limit,
                'repeated_routes':routes,
                'repeated_amount_series':[dict(src=str(r.src),dst=str(r.dst),date=r.day.date().isoformat(),
                                              sum_kzt=float(r.sum_kzt),n_tx=int(r.n_tx)) for r in repeat.itertuples(index=False)]}
    return df, patterns


def sensitivity(df):
    from pipeline.roles import assign, RoleConfig
    from pipeline.ranking import rank
    configurations = [(f'fan={fan};retain={low}',RoleConfig(high_fan=fan,low_ratio=low))
                      for fan in (3,5,8,10) for low in (.1,.2,.3)]
    configurations += [(f'transit_tolerance={tol}',RoleConfig(transit_tolerance=tol)) for tol in (.15,.25)]
    base = df.set_index('gid')
    base_top = set(df.sort_values(['priority_score','gid'],ascending=[False,True]).head(20).gid)
    roles, positions, top_hits, records = [], [], [], []
    for name, config in configurations:
        changed, _ = assign(df, config)
        changed, _ = rank(changed)
        changed = changed.sort_values(['priority_score','gid'],ascending=[False,True])
        changed['position'] = range(1,len(changed)+1)
        indexed = changed.set_index('gid').reindex(base.index)
        current_top = set(changed.head(20).gid)
        roles.append(indexed.role.eq(base.role).astype(float))
        positions.append(indexed.position)
        top_hits.append(indexed.position.le(20).astype(float))
        records.append({'scenario':name,'role_agreement':float(roles[-1].mean()),
                        'top20_jaccard':len(base_top & current_top)/len(base_top | current_top)})
    stats = pd.DataFrame({'gid':base.index,
                          'role_stability':pd.concat(roles,axis=1).mean(axis=1).to_numpy(),
                          'top20_frequency':pd.concat(top_hits,axis=1).mean(axis=1).to_numpy(),
                          'rank_min':pd.concat(positions,axis=1).min(axis=1).to_numpy(),
                          'rank_max':pd.concat(positions,axis=1).max(axis=1).to_numpy()})
    return stats, records


def robustness(df, graph):
    undirected = graph.to_undirected()
    original = list(nx.connected_components(undirected))
    ordered = df.sort_values(['priority_score','gid'],ascending=[False,True]).gid.tolist()
    def measure(removed):
        remaining = set(graph) - set(removed)
        comps = list(nx.connected_components(undirected.subgraph(remaining)))
        possible = sum(len(c & remaining)*(len(c & remaining)-1)/2 for c in original)
        connected = sum(len(c)*(len(c)-1)/2 for c in comps)
        return {'remaining_nodes':len(remaining),'components':len(comps),
                'largest_component':max(map(len,comps),default=0),
                'isolates':sum(len(c)==1 for c in comps),
                'connected_pair_retention':connected/possible if possible else 1.}
    random = np.random.default_rng(42)
    result = [{'removed_n':0,'removed_gids':[], **measure([])}]
    for count in (1,5,10,20):
        if count >= len(ordered):
            continue
        controls = [measure(random.choice(ordered,size=count,replace=False).tolist()) for _ in range(20)]
        result.append({'removed_n':count,'removed_gids':[str(g) for g in ordered[:count]],
                       **measure(ordered[:count]),
                       'random_mean_pair_retention':float(np.mean([c['connected_pair_retention'] for c in controls])),
                       'random_mean_largest_component':float(np.mean([c['largest_component'] for c in controls]))})
    return result
