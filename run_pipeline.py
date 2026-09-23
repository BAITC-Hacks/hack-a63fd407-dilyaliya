#!/usr/bin/env python3
import argparse
import json
import hashlib
import platform
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
import pandas as pd
from pipeline.load import load, require
from pipeline.metrics import calculate
from pipeline.roles import assign, ROLES
from pipeline.temporal import amount_matching
from pipeline.analytics import investigate, sensitivity, robustness
from pipeline.deliverables import write_demo
from pipeline.clustering import detect, summarize
from pipeline.ranking import rank, sensitivity as weight_sensitivity, WEIGHTS
from app.build import build

ROOT = Path(__file__).resolve().parent
NODE_COLUMNS = ['gid', 'role', 'role_score', 'cluster_id', 'priority_score', 'evidence']


def main():
    parser = argparse.ArgumentParser(description='Локальный AML-пайплайн')
    parser.add_argument('--data', type=Path, default=ROOT / 'data')
    parser.add_argument('--out', type=Path, default=ROOT / 'output')
    parser.add_argument('--top', type=int, default=30)
    args = parser.parse_args()
    require(args.top >= 20, '--top должен быть >=20')
    start = perf_counter()
    nodes, edges, tx = load(args.data)
    df, graph = calculate(nodes, edges, tx)
    temporal, matches = amount_matching(nodes, tx)
    df = df.merge(temporal, on="gid", validate="one_to_one")
    df, patterns = investigate(df, graph, tx, matches)
    df, thresholds = assign(df)
    membership, components = detect(graph)
    df['cluster_id'] = df.gid.map(membership)
    df, top = rank(df, args.top)
    stability, scenarios = sensitivity(df)
    stability = stability.rename(columns={'rank_min':'threshold_rank_min', 'rank_max':'threshold_rank_max'})
    df = df.merge(stability, on="gid", validate="one_to_one")
    df, top = rank(df, args.top)
    weight_scenarios, weight_summary = weight_sensitivity(df, args.top)
    ranges = weight_scenarios.groupby('gid')['rank'].agg(rank_min='min', rank_max='max')
    df = df.join(ranges, on='gid')
    impact = robustness(df, graph)
    clusters = summarize(df, edges)
    roles = df[NODE_COLUMNS]
    require(len(roles) == len(nodes) and roles.gid.is_unique, 'Потеря/дублирование узлов')
    for table in [roles, clusters, top]:
        require(not table.isna().any().any(), 'Пустые выходные поля')
    require(set(roles.role) <= ROLES, 'Недопустимая роль')
    require(roles.evidence.str.len().between(1, 200).all(), 'Evidence вне 1..200 символов')
    require(roles.role_score.between(0, 1).all() and roles.priority_score.between(0, 1).all(), 'Score вне 0..1')
    require(clusters.n_nodes.sum() == len(nodes), 'Потеря узлов в сообществах')
    require(clusters.n_seed.sum() == nodes.is_seed.sum(), 'Потеря seed')
    for group in df.groupby('cluster_id'):
        require(any(set(group[1].gid) <= component for component in components), 'Кластер объединил компоненты')
    args.out.mkdir(parents=True, exist_ok=True)
    for name, table in [('nodes_roles', roles), ('clusters', clusters), ('top_nodes', top)]:
        target = args.out / f'{name}.csv'
        table.to_csv(target, index=False, encoding='utf-8')
        require(pd.read_csv(target).shape == table.shape, f'Ошибка чтения {target}')
    df.to_parquet(args.out / 'node_metrics.parquet', index=False)
    matches.to_parquet(args.out / 'temporal_matches.parquet', index=False)
    stability.to_parquet(args.out / 'stability.parquet', index=False)
    weight_scenarios.to_csv(args.out / 'ranking_sensitivity.csv', index=False, encoding='utf-8')
    analytics = {'patterns':patterns, 'sensitivity':scenarios, 'robustness':impact}
    (args.out / 'analytics.json').write_text(json.dumps(analytics, ensure_ascii=False, indent=2), encoding='utf-8')
    demo = write_demo(df, args.out)
    build(df, edges, tx, graph, args.out / 'graph.html', clusters=clusters, analytics=analytics,
          demo=demo, top=top, stability=weight_summary)
    report = dict(nodes=len(nodes), edges=len(edges), transactions=len(tx), seeds=int(nodes.is_seed.sum()),
                  weak_components=len(components), smallest_component=min(map(len, components)),
                  components_with_edges=sum(len(c) > 1 or graph.subgraph(c).number_of_edges() > 0 for c in components),
                  isolated_nodes=sum(graph.degree(gid) == 0 for gid in graph),
                  clusters=len(clusters), depth4_leaves=int(df.is_depth4_leaf.sum()),
                  roles=df.role.value_counts().to_dict(), thresholds=thresholds,
                  ranking_weights=WEIGHTS, ranking_sensitivity=weight_summary,
                  transaction_dates_day_only=bool(tx.date.eq(tx.date.dt.normalize()).all()),
                  cycles=len(patterns['cycles']), repeated_routes=len(patterns['repeated_routes']),
                  sensitivity_scenarios=len(scenarios),
                  python_version=platform.python_version(),
                  dependency_versions={name:version(name) for name in ('pandas','numpy','networkx','pyarrow')},
                  input_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(args.data.glob('*.parquet'))},
                  elapsed_seconds=round(perf_counter()-start, 3))
    (args.out / 'run_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f'Готово: {args.out.resolve()} / graph.html')


if __name__ == '__main__':
    main()
