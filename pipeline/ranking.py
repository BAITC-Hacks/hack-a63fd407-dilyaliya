"""Feature-led ranking with a reproducible weight sensitivity audit."""
import numpy as np
import pandas as pd

ROLE_WEIGHT = {'coordinator': 1., 'consolidator': 1., 'distributor': 1.,
               'transit': .8, 'terminal': .35, 'peripheral': .1}
WEIGHTS = {'role': .15, 'volume': .25, 'fan': .25, 'seed': .10, 'context': .10, 'collection': .15}


def log_scale(series):
    values = np.log1p(series)
    return values / values.max() if values.max() > 0 else values * 0


def rank(df, top_n=30):
    df = df.copy()
    # Observed retention is useful only away from truncated leaves and seed inputs.
    retention = (1 - df.pass_through_ratio.clip(0, 1)).fillna(0)
    retention = retention.where(~df.is_seed & ~df.is_depth4_leaf, 0)
    features = {
        'role': df.role.map(ROLE_WEIGHT) * df.role_score,
        'volume': log_scale(df.volume),
        'fan': log_scale(df.fan_in + df.fan_out),
        'seed': df.seed_hops.map(lambda h: 1 / (1 + h) if h >= 0 else 0),
        'context': log_scale(df.reachable_seed_count),
        'collection': log_scale(df.fan_in) * retention,
    }
    for name, values in features.items():
        df[f'priority_{name}'] = WEIGHTS[name] * values
    columns = [f'priority_{name}' for name in WEIGHTS]
    df['priority_score'] = df[columns].sum(axis=1).clip(0, 1)
    ordered = df.sort_values(['priority_score', 'gid'], ascending=[False, True]).head(top_n).copy()
    ordered['rank'] = range(1, len(ordered) + 1)
    ordered['why'] = [
        f'{r.evidence}. Приоритет {r.priority_score:.4f}: роль {r.priority_role:.4f}, '
        f'объём {r.priority_volume:.4f}, связи {r.priority_fan:.4f}, '
        f'близость seed {r.priority_seed:.4f}, охват seed {r.priority_context:.4f}, '
        f'сбор с малой отдачей {r.priority_collection:.4f}. '
        f'Хопов: {r.seed_hops}; seed в пределах 4 шагов: {r.reachable_seed_count}; '
        f'транзакций вход/выход: {r.n_tx_in}/{r.n_tx_out}. '
        'Балл задаёт порядок ручной проверки, не вероятность виновности.'
        for r in ordered.itertuples(index=False)]
    return df, ordered[['rank', 'gid', 'role', 'priority_score', 'why']]


def sensitivity(df, top_n=30):
    """Change each weight ±20%, normalize; include a role-free control."""
    variants = {'baseline': WEIGHTS.copy()}
    for name in WEIGHTS:
        for factor in (.8, 1.2):
            weights = WEIGHTS.copy()
            weights[name] *= factor
            variants[f'{name}_{factor:.1f}'] = weights
    variants['without_role'] = {name: (0 if name == 'role' else weight) for name, weight in WEIGHTS.items()}
    base = df.sort_values(['priority_score', 'gid'], ascending=[False, True])
    base_ranks = {int(gid): rank for rank, gid in enumerate(base.gid, 1)}
    top_ids = set(base.head(top_n).gid)
    rows, summaries = [], []
    for variant, weights in variants.items():
        total = sum(weights.values())
        weights = {name: weight / total for name, weight in weights.items()}
        scores = sum(df[f'priority_{name}'] / WEIGHTS[name] * weight for name, weight in weights.items())
        ordered = df.assign(scenario_score=scores).sort_values(['scenario_score', 'gid'], ascending=[False, True])
        ranks = {int(gid): rank for rank, gid in enumerate(ordered.gid, 1)}
        overlap = len(top_ids & set(ordered.head(top_n).gid))
        summaries.append({'scenario': variant, 'weights': weights, 'top_overlap': overlap,
                          'top_size': len(top_ids), 'top_overlap_share': overlap / max(1, len(top_ids)),
                          'max_top_rank_shift': max((abs(ranks[int(gid)] - base_ranks[int(gid)]) for gid in top_ids), default=0)})
        for r in ordered.itertuples(index=False):
            rows.append({'scenario': variant, 'gid': r.gid, 'rank': ranks[int(r.gid)],
                         'baseline_rank': base_ranks[int(r.gid)], 'priority_score': r.scenario_score})
    return pd.DataFrame(rows), summaries
