"""Behavioral regressions for reported failures and graph accounting."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import pandas as pd
from pipeline.metrics import calculate
from pipeline.roles import assign
from pipeline.ranking import rank, sensitivity, WEIGHTS
from pipeline.clustering import summarize

ROOT = Path(__file__).resolve().parents[1]


def node(gid=1, **changes):
    row = dict(gid=gid, depth=1, is_seed=False, fan_in=2, fan_out=116,
               sum_in=100000., sum_out=200000., volume=300000.,
               pass_through_ratio=2., is_depth4_leaf=False, rapid_out_share=.4975,
               near_seed_count=0, seed_branch_count=2, reachable_seed_count=1,
               seed_hops=1, n_tx_in=2, n_tx_out=116)
    row.update(changes)
    return row


class RoleRegressions(unittest.TestCase):
    def test_fanout_survives_temporal_threshold(self):
        result, _ = assign(pd.DataFrame([node(i, rapid_out_share=share) for i, share in enumerate([0, .4975, .5, 1])]))
        self.assertEqual(set(result.role), {'distributor'})
        self.assertTrue(result.role_score.is_monotonic_increasing)

    def test_missing_input_can_still_distribute(self):
        result, _ = assign(pd.DataFrame([node(sum_in=0., pass_through_ratio=float('nan'))]))
        self.assertEqual(result.iloc[0].role, 'distributor')
        self.assertLessEqual(result.iloc[0].role_score, .55)
        self.assertIn('вход не наблюдается', result.iloc[0].evidence)

    def test_large_turnover_is_not_enough_for_coordinator(self):
        result, _ = assign(pd.DataFrame([node(fan_in=8, fan_out=8, volume=1e9)]))
        self.assertNotEqual(result.iloc[0].role, 'coordinator')

    def test_coordinator_needs_seeds_and_branches(self):
        rows = [node(i, fan_in=8, fan_out=8, near_seed_count=seeds, seed_branch_count=branches)
                for i, (seeds, branches) in enumerate([(1, 2), (2, 1), (2, 2)])]
        result, _ = assign(pd.DataFrame(rows))
        self.assertEqual(result.role.eq('coordinator').tolist(), [False, False, True])

    def test_very_asymmetric_fanout_keeps_distribution_role(self):
        result, _ = assign(pd.DataFrame([node(fan_in=8, fan_out=100, near_seed_count=5, seed_branch_count=8)]))
        self.assertEqual(result.iloc[0].role, 'distributor')

    def test_collection_bonus_excludes_seed_and_boundary(self):
        rows = [node(i, is_seed=seed, is_depth4_leaf=boundary, fan_in=13, fan_out=0,
                     sum_out=0, pass_through_ratio=0) for i, (seed, boundary) in enumerate([(False, False), (True, False), (False, True)])]
        df, _ = assign(pd.DataFrame(rows))
        ranked, _ = rank(df)
        self.assertGreater(ranked.iloc[0].priority_collection, 0)
        self.assertEqual(ranked.iloc[1].priority_collection, 0)
        self.assertEqual(ranked.iloc[2].priority_collection, 0)


class GraphRegressions(unittest.TestCase):
    def test_directed_paths_cycles_and_unreachable_node(self):
        nodes = pd.DataFrame({'gid': [1, 2, 3, 4, 5, 6], 'depth': [0, 0, 1, 2, 1, 1],
                              'is_seed': [True, True, False, False, False, False]})
        edges = pd.DataFrame({'src': [1, 2, 3, 4, 5, 3], 'dst': [3, 3, 4, 3, 1, 3],
                              'sum_kzt': [6000.] * 6, 'n_tx': [1] * 6})
        tx = edges[['src', 'dst', 'sum_kzt']].assign(date=pd.Timestamp('2026-07-01'))
        df, _ = calculate(nodes, edges, tx)
        records = df.set_index('gid')
        self.assertEqual(records.loc[4, 'seed_path'], ['1', '3', '4'])
        self.assertEqual(records.loc[4, 'near_seed_count'], 2)
        self.assertEqual(records.loc[3, 'reachable_seed_count'], 2)
        self.assertEqual(records.loc[3, 'fan_out'], 1)  # self-loop excluded
        self.assertEqual(records.loc[5, 'seed_path'], [])  # reverse edge is not a path
        self.assertEqual(records.loc[6, 'seed_hops'], -1)
        self.assertEqual(records.loc[1, 'seed_path'], ['1'])

    def test_cluster_boundary_accounting_and_isolate(self):
        df = pd.DataFrame([node(1, cluster_id=0, priority_score=.9, role='distributor'),
                           node(2, cluster_id=0, priority_score=.8, role='transit'),
                           node(3, cluster_id=1, priority_score=.7, role='terminal'),
                           node(4, cluster_id=2, priority_score=0., role='peripheral')])
        edges = pd.DataFrame({'src': [1, 2, 2, 3], 'dst': [2, 1, 3, 1], 'sum_kzt': [100., 50., 40., 60.]})
        summary = summarize(df, edges).set_index('cluster_id')
        self.assertEqual(summary.loc[0, 'sum_kzt_internal'], 150)
        text = summary.loc[0, 'hypothesis']
        self.assertIn('60.0%', text)
        self.assertIn('внешний вход 60, внешний выход 40', text)
        self.assertIn('веерное распределение', text)
        self.assertIn('изолированный узел', summary.loc[2, 'hypothesis'])


class EndToEndRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name)
        subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'run_pipeline.py'), '--out', str(cls.out)],
                       check=True, capture_output=True, cwd=ROOT)
        cls.df = pd.read_parquet(cls.out / 'node_metrics.parquet')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_reported_distributors_and_collection(self):
        df = self.df.set_index('gid')
        for gid in [100000002578405100, 100000002527114100]:
            self.assertEqual(df.loc[gid, 'role'], 'distributor')
            self.assertLessEqual(df.loc[gid, 'rank_max'], 30)
        self.assertEqual(df.loc[100000002398779100, 'role'], 'consolidator')
        self.assertLessEqual(df.loc[100000002398779100, 'rank_max'], 30)

    def test_all_csv_schemas_and_evidence(self):
        schemas = {'nodes_roles': ['gid', 'role', 'role_score', 'cluster_id', 'priority_score', 'evidence'],
                   'clusters': ['cluster_id', 'n_nodes', 'n_seed', 'sum_kzt_internal', 'top_gids', 'hypothesis'],
                   'top_nodes': ['rank', 'gid', 'role', 'priority_score', 'why']}
        for name, columns in schemas.items():
            table = pd.read_csv(self.out / f'{name}.csv')
            self.assertEqual(list(table.columns), columns)
            self.assertFalse(table.isna().any().any())
        self.assertEqual(len(self.df), 2248)
        self.assertTrue(self.df.evidence.str.len().between(1, 200).all())

    def test_priority_decomposition_and_sensitivity(self):
        sums = self.df[[f'priority_{key}' for key in WEIGHTS]].sum(axis=1)
        self.assertLess((sums - self.df.priority_score).abs().max(), 1e-12)
        self.assertTrue(self.df.priority_score.between(0, 1).all())
        scenarios = pd.read_csv(self.out / 'ranking_sensitivity.csv')
        self.assertEqual(scenarios.scenario.nunique(), 2 * len(WEIGHTS) + 2)
        for _, group in scenarios.groupby('scenario'):
            self.assertEqual(set(group.gid), set(self.df.gid))
            self.assertEqual(set(group['rank']), set(range(1, len(self.df)+1)))
        report = json.loads((self.out / 'run_report.json').read_text(encoding='utf-8'))
        for item in report['ranking_sensitivity']:
            self.assertAlmostEqual(sum(item['weights'].values()), 1)
        self.assertEqual(report['depth4_leaves'], 444)
        self.assertEqual(report['isolated_nodes'], 19)

    def test_seed_paths_preserve_int64_identifiers(self):
        edges = pd.read_parquet(ROOT / 'data/edges.parquet')
        pairs = {(str(r.src), str(r.dst)) for r in edges.itertuples(index=False)}
        seeds = set(self.df.loc[self.df.is_seed, 'gid'].astype(str))
        for row in self.df.itertuples(index=False):
            path = list(row.seed_path)
            if path:
                self.assertIn(path[0], seeds)
                self.assertEqual(path[-1], str(row.gid))
                self.assertEqual(len(path)-1, row.seed_hops)
                self.assertTrue(all(pair in pairs for pair in zip(path, path[1:])))

    def test_output_deterministic_under_input_reordering(self):
        shuffled = self.df.sample(frac=1, random_state=17)
        ranked, top = rank(shuffled)
        expected = pd.read_csv(self.out / 'top_nodes.csv')
        self.assertEqual(top.gid.tolist(), expected.gid.tolist())
        audit, _ = sensitivity(ranked)
        baseline = audit[audit.scenario.eq('baseline')].head(30)
        self.assertEqual(baseline.gid.tolist(), expected.gid.tolist())

    def test_standalone_html_contract(self):
        html = (self.out / 'graph.html').read_text(encoding='utf-8')
        self.assertNotIn('__GRAPH_', html)
        self.assertNotIn('<script src=', html)
        self.assertIn('"gid": "100000002578405100"', html)
        self.assertIn('id="top"', html)
        self.assertIn('id="node-detail"', html)


if __name__ == '__main__':
    unittest.main()
