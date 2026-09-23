import numpy as np

HIGH_FAN = 5
LOW_RATIO = .2
RAPID_SHARE = .5
ROLES = {'coordinator', 'consolidator', 'distributor', 'transit', 'terminal', 'peripheral'}


def assign(df):
    df = df.copy()
    threshold = float(df.volume.quantile(.9))
    def classify(r):
        ratio = r.pass_through_ratio
        comparable = min(r.fan_in, r.fan_out) > 0 and max(r.fan_in, r.fan_out) <= 2 * min(r.fan_in, r.fan_out)
        if r.fan_in >= HIGH_FAN and r.fan_out >= HIGH_FAN and r.volume >= threshold:
            role, score = 'coordinator', .85
        elif r.is_depth4_leaf and r.sum_in > 0:
            role, score = 'terminal', .25
        elif not r.is_seed and r.fan_in >= HIGH_FAN and ratio <= LOW_RATIO:
            role, score = 'consolidator', .8
        elif r.fan_out >= HIGH_FAN and r.rapid_out_share >= RAPID_SHARE and ratio >= .8:
            role, score = 'distributor', .75
        elif not r.is_seed and .8 <= ratio <= 1.2 and comparable and r.rapid_out_share >= RAPID_SHARE:
            role, score = 'transit', .75
        elif r.sum_in > 0 and r.fan_out == 0:
            role, score = 'terminal', .65
        else:
            role, score = 'peripheral', .4
        ratio_text = f'{ratio:.0%}' if np.isfinite(ratio) else 'не определено (вход=0)'
        evidence = f'Признаки {role}: вход от {r.fan_in}, выход к {r.fan_out}; отдаёт {ratio_text}; объём {r.volume:.0f} KZT'
        if role in ('transit', 'distributor'):
            evidence += f'; выход рядом с входом ≤24ч: {r.rapid_out_share:.0%}'
        if r.is_depth4_leaf:
            evidence += '; возможен артефакт обрыва графа на 4 колене'
        elif r.is_seed:
            evidence += '; вход seed неполон'
            score = min(score, .55)
        elif role == 'terminal':
            evidence += '; нет выхода в выборке'
        return role, score, evidence
    result = [classify(r) for r in df.itertuples(index=False)]
    df[['role', 'role_score', 'evidence']] = result
    df['role_score'] = df.role_score.astype(float)
    return df, {'high_fan': HIGH_FAN, 'coordinator_volume_p90_kzt': threshold,
                'low_ratio': LOW_RATIO, 'rapid_share': RAPID_SHARE}
