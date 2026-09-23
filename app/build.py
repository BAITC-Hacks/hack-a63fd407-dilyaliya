import json
import math
from pathlib import Path


def build(df, edges, destination):
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
    # gid передаём строками: int64 может выходить за точность JavaScript Number.
    for r in records:
        r['gid'] = str(r['gid'])
    links = [dict(src=str(r.src), dst=str(r.dst), sum_kzt=float(r.sum_kzt), n_tx=int(r.n_tx))
             for r in edges.itertuples(index=False)]
    payload = json.dumps({'nodes': records, 'edges': links}, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    template = Path(__file__).with_name('template.html').read_text(encoding='utf-8')
    Path(destination).write_text(template.replace('__GRAPH_DATA__', payload), encoding='utf-8')
