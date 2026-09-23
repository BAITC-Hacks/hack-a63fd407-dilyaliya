import unittest
import networkx as nx
import pandas as pd
from pipeline.temporal import amount_matching
from pipeline.roles import assign
from pipeline.metrics import calculate
from pipeline.analytics import investigate, robustness, sensitivity
from pipeline.ranking import rank


class AnalyticsTests(unittest.TestCase):
    def fixture(self, transactions):
        tx=pd.DataFrame(transactions,columns=['src','dst','date','sum_kzt'])
        tx['date']=pd.to_datetime(tx.date)
        ids=sorted(set(tx.src)|set(tx.dst))
        nodes=pd.DataFrame({'gid':ids,'depth':[0 if i==min(ids) else 1 for i in ids],
                            'is_seed':[i==min(ids) for i in ids]})
        edges=tx.groupby(['src','dst']).agg(sum_kzt=('sum_kzt','sum'),n_tx=('sum_kzt','size')).reset_index()
        df,g=calculate(nodes,edges,tx)
        t,m=amount_matching(nodes,tx)
        return df.merge(t,on='gid'),g,tx,m

    def test_fifo_conserves_amount_and_ignores_future(self):
        df,g,tx,m=self.fixture([(1,2,'2026-07-02',6000),(2,3,'2026-07-01',5000),
                                (2,3,'2026-07-02',5000),(2,3,'2026-07-03',5000),
                                (2,3,'2026-07-07',5000)])
        for scenario in ('strict','same_day_possible'):
            subset=m[(m.gid==2)&(m.scenario==scenario)]
            self.assertLessEqual(subset.matched_kzt.sum(),6000)
            self.assertNotIn('row:2',subset.out_ref.tolist())
            self.assertNotIn('row:5',subset.out_ref.tolist())
            self.assertTrue(subset.lag_days.between(0,2).all())
            for ref,group in subset.groupby('out_ref'):
                self.assertLessEqual(group.matched_kzt.sum(),5000)
        strict=m[(m.gid==2)&m.scenario.eq('strict')]
        self.assertFalse(strict.lag_days.eq(0).any())

    def test_strong_fan_out_not_lost_below_time_threshold(self):
        rows=[]
        for gid,fan,fast in [(1,116,.497481),(2,5,0),(3,50,.9)]:
            rows.append(dict(gid=gid,is_seed=False,is_depth4_leaf=False,fan_in=2,fan_out=fan,
                             sum_in=100,sum_out=300,volume=400,pass_through_ratio=3,
                             fifo_same_day_possible_share=fast,fifo_strict_share=fast/2))
        df,_=assign(pd.DataFrame(rows))
        self.assertEqual(df.role.tolist(),['distributor']*3)
        self.assertGreater(df.iloc[0].role_score,df.iloc[1].role_score)

    def test_patterns_and_real_sensitivity(self):
        df,g,tx,m=self.fixture([(1,2,'2026-07-01',5000),(2,3,'2026-07-02',5000),
                                (1,2,'2026-07-05',5000),(2,3,'2026-07-06',5000),
                                (3,1,'2026-07-07',5000)])
        df,patterns=investigate(df,g,tx,m)
        self.assertEqual(len(patterns['cycles']),1)
        self.assertEqual(patterns['cycles'][0]['gids'],['1','2','3'])
        route=next(r for r in patterns['repeated_routes'] if r['gids']==['1','2','3'])
        self.assertEqual(route['matched_kzt'],10000)
        df,_=assign(df);df,_=rank(df)
        stats,scenarios=sensitivity(df)
        self.assertEqual(len(scenarios),14)
        self.assertTrue(stats.role_stability.between(0,1).all())
        base=next(s for s in scenarios if s['scenario']=='fan=5;retain=0.2')
        self.assertEqual(base['role_agreement'],1)
        self.assertEqual(base['top20_jaccard'],1)

    def test_removal_of_bridge_fragments_remaining_nodes(self):
        graph=nx.DiGraph([(1,2),(2,3),(3,4),(4,5)])
        df=pd.DataFrame({'gid':[3,1,2,4,5],'priority_score':[1,.4,.3,.2,.1]})
        result=robustness(df,graph)
        one=next(r for r in result if r['removed_n']==1)
        self.assertEqual(one['components'],2)
        self.assertAlmostEqual(one['connected_pair_retention'],2/6)
