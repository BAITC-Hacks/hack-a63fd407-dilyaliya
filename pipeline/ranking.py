import numpy as np

ROLE_WEIGHT = {'coordinator': 1., 'consolidator': .95, 'distributor': .75,
               'transit': .65, 'terminal': .45, 'peripheral': .1}


def rank(df, top_n=30):
    df = df.copy()
    def log_scale(series):
        values = np.log1p(series)
        return values / values.max() if values.max() > 0 else values * 0
    df['priority_role'] = .4 * df.role.map(ROLE_WEIGHT) * df.role_score
    df['priority_volume'] = .25 * log_scale(df.volume)
    df['priority_fan'] = .2 * log_scale(df.fan_in + df.fan_out)
    df['priority_seed'] = .15 * df.seed_hops.map(lambda h: 1 / (1 + h) if h >= 0 else 0)
    df['priority_score'] = df[['priority_role', 'priority_volume', 'priority_fan', 'priority_seed']].sum(axis=1).clip(0, 1)
    ordered = df.sort_values(['priority_score', 'gid'], ascending=[False, True]).head(top_n).copy()
    ordered['rank'] = range(1, len(ordered) + 1)
    ordered['why'] = [f'{r.evidence}. Приоритет {r.priority_score:.4f}: вклад роли {r.priority_role:.4f}, '
                      f'объёма {r.priority_volume:.4f}, связей {r.priority_fan:.4f}, '
                      f'близости к seed {r.priority_seed:.4f} (направленных хопов: {r.seed_hops}). '
                      f'Транзакций вход/выход: {r.n_tx_in}/{r.n_tx_out}. '
                      'Выше балл — больше оснований проверить структуру потока; это не вероятность виновности.'
                      for r in ordered.itertuples(index=False)]
    return df, ordered[['rank', 'gid', 'role', 'priority_score', 'why']]
