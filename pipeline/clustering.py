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
    internal = edges[edges.src.map(membership).eq(edges.dst.map(membership))].copy()
    internal['cluster_id'] = internal.src.map(membership)
    totals = internal.groupby('cluster_id').sum_kzt.sum()
    rows = []
    for cid, group in df.groupby('cluster_id', sort=True):
        top = group.sort_values(['priority_score', 'gid'], ascending=[False, True]).head(5)
        main = top.iloc[0]
        rows.append(dict(cluster_id=int(cid), n_nodes=len(group), n_seed=int(group.is_seed.sum()),
                         sum_kzt_internal=float(totals.get(cid, 0)), top_gids=json.dumps(top.gid.tolist()),
                         hypothesis=f'Гипотеза: сообщество из {len(group)} узлов, seed: {int(group.is_seed.sum())}; '
                         f'приоритетный узел {int(main.gid)} имеет признаки {main.role}; требует проверки.'))
    return pd.DataFrame(rows)
