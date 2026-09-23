from collections import deque
import networkx as nx
import numpy as np
import pandas as pd


def calculate(nodes, edges, tx):
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes.gid.tolist())
    for r in edges.itertuples(index=False):
        graph.add_edge(r.src, r.dst, weight=float(r.sum_kzt), n_tx=int(r.n_tx))
    df = nodes.copy()
    for name, values in [('in_degree', dict(graph.in_degree())), ('out_degree', dict(graph.out_degree())),
                         ('sum_in', dict(graph.in_degree(weight='weight'))),
                         ('sum_out', dict(graph.out_degree(weight='weight'))),
                         ('n_tx_in', dict(graph.in_degree(weight='n_tx'))),
                         ('n_tx_out', dict(graph.out_degree(weight='n_tx')))]:
        df[name] = df.gid.map(values)
    # Self-transfers are activity, but not a distinct counterparty.
    df['fan_in'] = df.gid.map({gid: sum(src != gid for src in graph.predecessors(gid)) for gid in graph})
    df['fan_out'] = df.gid.map({gid: sum(dst != gid for dst in graph.successors(gid)) for gid in graph})
    df['zero_sum_in'] = df.sum_in.eq(0)
    df['pass_through_ratio'] = df.sum_out / df.sum_in.replace(0, np.nan)
    df['is_depth4_leaf'] = df.depth.eq(4) & df.out_degree.eq(0)
    df['volume'] = df.sum_in + df.sum_out
    events = pd.concat([tx[['src', 'date']].rename(columns={'src': 'gid'}),
                        tx[['dst', 'date']].rename(columns={'dst': 'gid'})])
    dates = events.groupby('gid').date.agg(first_tx='min', last_tx='max')
    df = df.join(dates, on='gid')
    df['activity_span_hours'] = (df.last_tx - df.first_tx).dt.total_seconds() / 3600
    # Доля исходящей суммы, которой предшествует хотя бы один вход за 0..24 ч.
    # Это временное соседство, не трассировка одних и тех же денег.
    incoming = {gid: np.sort(group.date.to_numpy()) for gid, group in tx.groupby('dst')}
    rapid = {}
    for gid, group in tx.groupby('src'):
        ins = incoming.get(gid, np.array([], dtype='datetime64[ns]'))
        outs = group.date.to_numpy()
        pos = np.searchsorted(ins, outs, side='right') - 1
        ok = pos >= 0
        if len(ins):
            lag = outs - ins[np.maximum(pos, 0)]
            ok &= lag <= np.timedelta64(24, 'h')
        rapid[gid] = float(group.loc[ok, 'sum_kzt'].sum() / group.sum_kzt.sum())
    df['rapid_out_share'] = df.gid.map(rapid).fillna(0)
    seeds = sorted(int(gid) for gid in nodes.loc[nodes.is_seed, 'gid'])
    hops = {gid: 0 for gid in seeds}
    paths = {gid: [str(gid)] for gid in seeds}
    queue = deque(sorted(hops))
    while queue:
        src = queue.popleft()
        for dst in sorted(graph.successors(src)):
            if dst not in hops:
                hops[dst] = hops[src] + 1
                paths[dst] = paths[src] + [str(dst)]
                queue.append(dst)
    df['seed_hops'] = df.gid.map(hops).fillna(-1).astype(int)
    df['seed_path'] = [paths.get(gid, []) for gid in df.gid]
    # Bound context to the observation horizon; cycles cannot multiply seeds.
    reach = {gid: set() for gid in graph}
    near = {gid: set() for gid in graph}
    upstream = set()
    for seed in seeds:
        distances = nx.single_source_shortest_path_length(graph, seed, cutoff=4)
        for gid, distance in distances.items():
            if distance <= 3:
                upstream.add(gid)
            if gid != seed:
                reach[gid].add(seed)
                if distance <= 2:
                    near[gid].add(seed)
    df['reachable_seed_count'] = df.gid.map({gid: len(values) for gid, values in reach.items()})
    df['near_seed_count'] = df.gid.map({gid: len(values) for gid, values in near.items()})
    df['seed_branch_count'] = df.gid.map({
        gid: sum(src != gid and src in upstream for src in graph.predecessors(gid)) for gid in graph
    })
    return df, graph
