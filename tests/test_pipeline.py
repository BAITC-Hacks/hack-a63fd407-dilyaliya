"""Проверки граничных случаев и контракта на реальной выгрузке."""
import tempfile
import unittest
from pathlib import Path
import networkx as nx
import pandas as pd
from pipeline.load import load
from pipeline.metrics import calculate
from pipeline.roles import assign
from pipeline.clustering import detect

ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    def test_boundary_seed_and_isolate(self):
        rows = []
        for gid, depth, seed, fin, fout, sin, sout in [
            (1, 4, False, 10, 0, 100000, 0),
            (2, 0, True, 10, 0, 100000, 0),
            (3, 2, False, 10, 0, 100000, 0),
            (4, 1, False, 0, 0, 0, 0)]:
            rows.append(dict(gid=gid, depth=depth, is_seed=seed, fan_in=fin, fan_out=fout,
                             sum_in=sin, sum_out=sout, volume=sin+sout,
                             pass_through_ratio=sout/sin if sin else float('nan'),
                             is_depth4_leaf=depth==4 and fout==0, rapid_out_share=0))
        result, _ = assign(pd.DataFrame(rows))
        self.assertEqual(result.role.tolist(), ['terminal', 'terminal', 'consolidator', 'peripheral'])
        self.assertIn('возможен артефакт обрыва графа на 4 колене', result.iloc[0].evidence)
        self.assertLessEqual(result.iloc[0].role_score, .25)
        self.assertLessEqual(result.iloc[1].role_score, .55)

    def test_temporal_direction_and_isolate(self):
        nodes = pd.DataFrame({'gid': [1, 2, 3, 4], 'depth': [0, 1, 2, 0], 'is_seed': [True, False, False, True]})
        edges = pd.DataFrame({'src': [1, 2], 'dst': [2, 3], 'sum_kzt': [6000., 6000.], 'n_tx': [1, 1]})
        tx = pd.DataFrame({'src': [1, 2], 'dst': [2, 3], 'sum_kzt': [6000., 6000.],
                           'date': pd.to_datetime(['2026-07-03', '2026-07-01'])})
        df, graph = calculate(nodes, edges, tx)
        self.assertEqual(df.set_index('gid').loc[2, 'rapid_out_share'], 0)
        self.assertEqual(df.set_index('gid').loc[4, 'in_degree'], 0)
        membership, _ = detect(graph)
        self.assertNotEqual(membership[1], membership[4])
        tx.loc[1, 'date'] = pd.Timestamp('2026-07-04')
        df, _ = calculate(nodes, edges, tx)
        self.assertEqual(df.set_index('gid').loc[2, 'rapid_out_share'], 1)

    def test_real_contract_and_corruption(self):
        nodes, edges, tx = load(ROOT / 'data')
        out = pd.read_csv(ROOT / 'output/nodes_roles.csv')
        self.assertEqual(len(out), 2248)
        self.assertEqual(set(out.gid), set(nodes.gid))
        self.assertFalse(out.isna().any().any())
        self.assertTrue(out.evidence.str.len().between(1, 200).all())
        top = pd.read_csv(ROOT / 'output/top_nodes.csv')
        self.assertGreaterEqual(len(top), 20)
        self.assertTrue(top.priority_score.is_monotonic_decreasing)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            nodes.to_parquet(path / 'nodes.parquet')
            tx.to_parquet(path / 'transactions.parquet')
            edges = edges.copy()
            edges.iloc[0, edges.columns.get_loc('n_tx')] += 1
            edges.to_parquet(path / 'edges.parquet')
            with self.assertRaisesRegex(ValueError, 'n_tx'):
                load(path)


if __name__ == '__main__':
    unittest.main()
