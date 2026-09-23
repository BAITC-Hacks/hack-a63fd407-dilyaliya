"""Explicit hypotheses, independent of individual client identifiers."""
import numpy as np

HIGH_FAN = 5
LOW_RATIO = .2
RAPID_SHARE = .5
ROLES = {'coordinator', 'consolidator', 'distributor', 'transit', 'terminal', 'peripheral'}


def assign(df):
    df = df.copy()
    threshold = float(df.volume.quantile(.9)) if len(df) else 0.

    def classify(r):
        ratio = r.pass_through_ratio
        comparable = min(r.fan_in, r.fan_out) > 0 and max(r.fan_in, r.fan_out) <= 2 * min(r.fan_in, r.fan_out)
        near_seeds = getattr(r, 'near_seed_count', 0)
        branches = getattr(r, 'seed_branch_count', 0)
        if r.is_depth4_leaf and r.sum_in > 0:
            role, score = 'terminal', .25
        elif not r.is_seed and r.fan_in >= HIGH_FAN and ratio <= LOW_RATIO:
            role, score = 'consolidator', .8
        elif (r.fan_in >= HIGH_FAN and r.fan_out >= HIGH_FAN and comparable
              and r.volume >= threshold and near_seeds >= 2 and branches >= 2):
            role, score = 'coordinator', .7 + .1 * min(1, (near_seeds - 2) / 3)
        elif r.fan_out >= HIGH_FAN and (r.fan_out >= 2 * max(1, r.fan_in)
                                       or (np.isfinite(ratio) and ratio >= .8)):
            role, score = 'distributor', .65 + .15 * r.rapid_out_share
            if r.sum_in == 0:
                score = min(score, .55)
        elif not r.is_seed and .8 <= ratio <= 1.2 and comparable and r.rapid_out_share >= RAPID_SHARE:
            role, score = 'transit', .65 + .15 * r.rapid_out_share
        elif r.sum_in > 0 and r.fan_out == 0:
            role, score = 'terminal', .65
        else:
            role, score = 'peripheral', .4
        ratio_text = f'{ratio:.1%}' if np.isfinite(ratio) else 'н/д (вход=0)'
        evidence = f'{role}: вход от {r.fan_in}, выход к {r.fan_out}; отдаёт {ratio_text}; оборот {r.volume:.0f} KZT'
        if role == 'coordinator':
            evidence += f'; seed ≤2 шага: {near_seeds}, входных ветвей: {branches}'
        if role in ('transit', 'distributor'):
            evidence += f'; рядом с входом ≤24ч: {r.rapid_out_share:.1%}'
        if r.is_depth4_leaf:
            evidence += '; возможен артефакт обрыва графа на 4 колене'
        if r.is_seed:
            evidence += '; вход seed неполон'
            score = min(score, .55)
        elif r.sum_in == 0 and r.fan_out:
            evidence += '; вход не наблюдается'
        elif role == 'terminal' and not r.is_depth4_leaf:
            evidence += '; нет выхода в выборке'
        return role, score, evidence

    result = [classify(r) for r in df.itertuples(index=False)]
    df[['role', 'role_score', 'evidence']] = result
    df['role_score'] = df.role_score.astype(float)
    return df, {'high_fan': HIGH_FAN, 'coordinator_volume_p90_kzt': threshold,
                'coordinator_near_seeds_min': 2, 'coordinator_seed_hops_max': 2,
                'coordinator_branches_min': 2, 'coordinator_fan_balance_max': 2,
                'distributor_fan_ratio_min': 2, 'distributor_pass_ratio_alternative': .8,
                'low_ratio': LOW_RATIO, 'rapid_share_transit_only': RAPID_SHARE}
