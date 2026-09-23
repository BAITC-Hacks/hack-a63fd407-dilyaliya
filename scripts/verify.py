#!/usr/bin/env python3
"""Независимые проверки результатов и повторяемости полного запуска."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
SCHEMAS={
    'nodes_roles':['gid','role','role_score','cluster_id','priority_score','evidence'],
    'clusters':['cluster_id','n_nodes','n_seed','sum_kzt_internal','top_gids','hypothesis'],
    'top_nodes':['rank','gid','role','priority_score','why']}


def verify():
    start=time.perf_counter()
    subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,check=True)
    checks=[]
    with tempfile.TemporaryDirectory(prefix='aml-verify-') as temporary:
        directories=[Path(temporary)/'first',Path(temporary)/'second']
        for directory in directories:
            subprocess.run([sys.executable,str(ROOT/'run_pipeline.py'),'--out',str(directory)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
        first,second=directories
        for name,columns in SCHEMAS.items():
            table=pd.read_csv(first/f'{name}.csv')
            assert table.columns.tolist()==columns and not table.isna().any().any(), name
            assert (first/f'{name}.csv').read_bytes()==(second/f'{name}.csv').read_bytes(), name+' reproducibility'
        checks.append('Exact CSV schemas, nonempty mandatory fields, byte-identical repeat runs')
        roles=pd.read_csv(first/'nodes_roles.csv')
        top=pd.read_csv(first/'top_nodes.csv')
        source=pd.read_parquet(ROOT/'data/nodes.parquet')
        assert len(roles)==len(source)==2248 and set(roles.gid)==set(source.gid)
        assert roles.evidence.str.len().between(1,200).all()
        assert roles.role_score.between(0,1).all() and roles.priority_score.between(0,1).all()
        assert len(top)>=20 and top['rank'].tolist()==list(range(1,len(top)+1))
        assert top.priority_score.is_monotonic_decreasing
        checks.append('All nodes preserved; scores, evidence length, top ranks valid')
        tx=pd.read_parquet(ROOT/'data/transactions.parquet').reset_index(drop=True)
        tx['ref']=['row:'+str(i+1) for i in range(len(tx))]
        tx=tx.set_index('ref')
        ledger=pd.read_parquet(first/'temporal_matches.parquet')
        for scenario,matched in ledger.groupby('scenario'):
            assert matched.matched_kzt.gt(0).all()
            assert matched.lag_days.between(1 if scenario=='strict' else 0,2).all()
            for direction in ('in','out'):
                totals=matched.groupby(['gid',direction+'_ref']).matched_kzt.sum()
                for (gid,ref),amount in totals.items():
                    original=tx.loc[ref]
                    assert amount<=original.sum_kzt+.005
                    assert gid==original['dst' if direction=='in' else 'src']
        checks.append('FIFO preserves amounts per node/ref/scenario and valid temporal direction')
        metrics=pd.read_parquet(first/'node_metrics.parquet')
        assert metrics.loc[metrics.is_depth4_leaf,'evidence'].str.contains('возможен артефакт').all()
        assert metrics.loc[metrics.is_depth4_leaf,'role_score'].le(.25).all()
        assert not ((metrics.role=='peripheral') & (metrics.fan_out>=5)).any()
        assert metrics.role_stability.between(0,1).all()
        clusters=pd.read_csv(first/'clusters.csv')
        edges=pd.read_parquet(ROOT/'data/edges.parquet')
        membership=roles.set_index('gid').cluster_id
        for row in clusters.itertuples(index=False):
            internal=edges[edges.src.map(membership).eq(row.cluster_id)&edges.dst.map(membership).eq(row.cluster_id)]
            assert np.isclose(row.sum_kzt_internal,internal.sum_kzt.sum())
        checks.append('Boundary uncertainty, strong fan-out, stability and cluster sums verified')
        for file in ('node_metrics.parquet','temporal_matches.parquet','stability.parquet','analytics.json','graph.html','demo_cases.json','ranking_sensitivity.csv','assistant_data.json'):
            assert (first/file).read_bytes()==(second/file).read_bytes(),file+' reproducibility'
        checks.append('Analytical artifacts and HTML deterministic')
        report={'status':'passed','checks':checks,'elapsed_seconds':round(time.perf_counter()-start,3),
                'pipeline_seconds':json.loads((first/'run_report.json').read_text())['elapsed_seconds'],
                'csv_sha256':{name:hashlib.sha256((first/f'{name}.csv').read_bytes()).hexdigest() for name in SCHEMAS}}
    (ROOT/'output').mkdir(exist_ok=True)
    (ROOT/'output/validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    verify()
