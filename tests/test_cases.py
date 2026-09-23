import unittest
import networkx as nx
from app.cases import case_context, missing_data


class CasesTests(unittest.TestCase):
    def test_directed_paths_and_no_path(self):
        graph = nx.DiGraph([(1, 3), (2, 3), (3, 4), (4, 3)])
        graph.add_node(5)
        rows = [dict(gid=i, is_seed=i in (1, 2), is_depth4_leaf=i==4,
                     zero_sum_in=False, pass_through_ratio=0, sum_in=100, sum_out=0,
                     fan_in=1, fan_out=0) for i in range(1, 6)]
        cases = case_context(rows, graph)
        self.assertEqual(cases['4']['paths'], [{'seed':'1','gids':['1','3','4']}, {'seed':'2','gids':['2','3','4']}])
        self.assertEqual(cases['5']['paths'], [])
        self.assertEqual(cases['1']['paths'][0]['gids'], ['1'])
        self.assertTrue(any('четвёртое' in r['request'] for r in cases['4']['requests']))
        self.assertTrue(any('полный входящий' in r['request'] for r in cases['1']['requests']))

    def test_temporal_request_and_unknown_ratio(self):
        row=dict(is_seed=False,is_depth4_leaf=False,zero_sum_in=True,
                 pass_through_ratio=None,sum_in=0,sum_out=100,fan_in=0,fan_out=2)
        requests=missing_data(row)
        self.assertTrue(any('полный входящий' in r['request'] for r in requests))
        self.assertFalse(any('часовой пояс' in r['request'] for r in requests))
        row.update(sum_in=100,zero_sum_in=False,pass_through_ratio=1)
        self.assertTrue(any('часовой пояс' in r['request'] for r in missing_data(row)))
