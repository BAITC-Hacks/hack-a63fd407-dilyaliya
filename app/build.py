import json
import hashlib
from app.cases import case_context
import math
from pathlib import Path


def build(df, edges, destination, clusters=None, top=None, stability=None, tx=None, graph=None):
    records = json.loads(df.to_json(orient='records', date_format='iso'))
    by_gid = {r['gid']: r for r in records}
    groups = list(df.groupby('cluster_id', sort=True))
    cols = max(1, math.ceil(math.sqrt(len(groups))))
    for i, (_, group) in enumerate(groups):
        ordered = group.sort_values(['priority_score', 'gid'], ascending=[False, True])
        for j, gid in enumerate(ordered.gid):
            angle = j * math.pi * (3 - math.sqrt(5))
            radius = 9 * math.sqrt(j)
            by_gid[gid]['x'] = (i % cols) * 330 + radius * math.cos(angle)
            by_gid[gid]['y'] = (i // cols) * 330 + radius * math.sin(angle)
    cases = case_context(records, graph)
    # gid передаём строками: int64 может выходить за точность JavaScript Number.
    for r in records:
        r['gid'] = str(r['gid'])
    links = [dict(src=str(r.src), dst=str(r.dst), sum_kzt=float(r.sum_kzt), n_tx=int(r.n_tx))
             for r in edges.itertuples(index=False)]
    cluster_records = [] if clusters is None else clusters.to_dict(orient='records')
    for cluster in cluster_records:
        cluster['top_gids'] = [str(gid) for gid in json.loads(cluster['top_gids'])]
    top_records = [] if top is None else top.to_dict(orient='records')
    for row in top_records:
        row['gid'] = str(row['gid'])
    transactions = [dict(ref=f'row:{i+1}', src=str(r.src), dst=str(r.dst), date=r.date.isoformat(), sum_kzt=float(r.sum_kzt))
                    for i, r in enumerate(tx.itertuples(index=False))]
    fingerprint = hashlib.sha256(json.dumps({'nodes': [(r['gid'], r['depth'], r['is_seed']) for r in records],
                                            'edges': links, 'transactions': transactions}, sort_keys=True).encode()).hexdigest()
    payload = json.dumps({'nodes': records, 'edges': links, 'clusters': cluster_records,
                          'transactions': transactions, 'cases': cases, 'fingerprint': fingerprint,
                          'top': top_records, 'stability': stability or []},
                         ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    template = Path(__file__).with_name('template.html').read_text(encoding='utf-8')
    template = template.replace('__GRAPH_STYLE__', Path(__file__).with_name('style.css').read_text(encoding='utf-8'))
    template = template.replace('__GRAPH_SCRIPT__', Path(__file__).with_name('view.js').read_text(encoding='utf-8'))
    template = template.replace('__CASE_JS__', Path(__file__).with_name('cases.js').read_text(encoding='utf-8'))
    Path(destination).write_text(template.replace('__GRAPH_DATA__', payload), encoding='utf-8')
