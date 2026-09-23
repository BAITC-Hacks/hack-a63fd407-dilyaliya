import json
import networkx as nx
import pandas as pd


def detect(graph):
    undirected = nx.Graph()
    undirected.add_nodes_from(sorted(graph.nodes))
    for src, dst, data in graph.edges(data=True):
        previous = undirected.get_edge_data(src, dst, {}).get('weight', 0)
        undirected.add_edge(src, dst, weight=previous + data['weight'])
    communities = []
    components = sorted(nx.connected_components(undirected), key=min)
    for component in components:
        subgraph = undirected.subgraph(sorted(component)).copy()
        if subgraph.size(weight='weight') == 0:
            communities.extend([{gid} for gid in sorted(component)])
        else:
            communities.extend(nx.community.louvain_communities(subgraph, weight='weight', resolution=1, seed=42))
    communities.sort(key=min)
    return {gid: cid for cid, group in enumerate(communities) for gid in group}, components


def summarize(df, edges):
    membership = df.set_index('gid').cluster_id
    source_clusters, target_clusters = edges.src.map(membership), edges.dst.map(membership)
    rows = []
    for cid, group in df.groupby('cluster_id', sort=True):
        top = group.sort_values(['priority_score', 'gid'], ascending=[False, True]).head(5)
        source_here, target_here = source_clusters.eq(cid), target_clusters.eq(cid)
        inside = float(edges.loc[source_here & target_here, 'sum_kzt'].sum())
        incoming = float(edges.loc[~source_here & target_here, 'sum_kzt'].sum())
        outgoing = float(edges.loc[source_here & ~target_here, 'sum_kzt'].sum())
        touched = inside + incoming + outgoing
        share = inside / touched if touched else 0
        outgoing_edges = edges.loc[source_here]
        recipients = outgoing_edges.groupby('dst').sum_kzt.sum().reset_index().sort_values(
            ['sum_kzt', 'dst'], ascending=[False, True]).head(3)
        recipients_text = ', '.join(f'{int(r.dst)} ({r.sum_kzt:,.0f} KZT)' for r in recipients.itertuples(index=False)) or 'нет'
        collectors = group[group.role.eq('consolidator')]
        distributors = group[group.role.eq('distributor')]
        transits = group[group.role.eq('transit')]
        signals = []
        if len(collectors):
            signals.append(f'сбор/накопление: {len(collectors)} узл., наблюдаемый вход {collectors.sum_in.sum():,.0f} KZT')
        if len(distributors):
            signals.append(f'веерное распределение: {len(distributors)} узл., максимум {distributors.fan_out.max()} получателей')
        if len(transits):
            signals.append(f'транзит: {len(transits)} узл. с близкими входом/выходом и временным соседством')
        if not touched:
            purpose = 'изолированный узел без наблюдаемых переводов; назначение не определяется'
        elif signals:
            purpose = '; '.join(signals)
        elif outgoing > 1.5 * incoming and outgoing > inside:
            purpose = 'преимущественно передача средств в другие сообщества'
        elif incoming > 1.5 * outgoing and incoming > inside:
            purpose = 'преимущественно получение из других сообществ; накопление не доказано'
        elif incoming > 0 and outgoing > 0 and .8 <= outgoing / incoming <= 1.2:
            purpose = 'сбалансированный обмен между сообществами; проверить временную последовательность'
        else:
            purpose = 'смешанный внутренний обмен; выраженное назначение не установлено'
        boundary = int(group.is_depth4_leaf.sum())
        hypothesis = (f'Гипотеза: {purpose}. Внутренние переводы {inside:,.0f} KZT '
                      f'({share:.1%} суммы внутренних и пересекающих границу переводов); '
                      f'внешний вход {incoming:,.0f}, внешний выход {outgoing:,.0f} KZT. '
                      f'Основные получатели переводов участников: {recipients_text}. '
                      f'Граница 4-го колена: {boundary}/{len(group)} узл. '
                      'Проверить полные выписки и назначения платежей; роль сообщества не доказана.')
        rows.append(dict(cluster_id=int(cid), n_nodes=len(group), n_seed=int(group.is_seed.sum()),
                         sum_kzt_internal=inside, top_gids=json.dumps(top.gid.tolist()), hypothesis=hypothesis))
    return pd.DataFrame(rows)
