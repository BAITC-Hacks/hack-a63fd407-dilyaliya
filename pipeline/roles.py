"""Версионируемые правила ролей. Score — сила правила, не вероятность."""
from dataclasses import asdict, dataclass
import numpy as np

ROLES = {'coordinator', 'consolidator', 'distributor', 'transit', 'terminal', 'peripheral'}
RULE_VERSION = '3.0'


@dataclass(frozen=True)
class RoleConfig:
    high_fan: int = 5
    low_ratio: float = .2
    transit_tolerance: float = .2
    fan_balance: float = 2.
    rapid_share: float = .5
    coordinator_quantile: float = .9
    coordinator_near_seeds: int = 2
    coordinator_branches: int = 2


def assign(df, config=None):
    config = config or RoleConfig()
    df = df.copy()
    threshold = float(df.volume.quantile(config.coordinator_quantile))
    def classify(r):
        ratio = r.pass_through_ratio
        fast = float(getattr(r, 'fifo_same_day_possible_share', 0))
        strict = float(getattr(r, 'fifo_strict_share', 0))
        fan_strength = min(1., max(r.fan_in, r.fan_out) / (4 * config.high_fan))
        comparable = min(r.fan_in, r.fan_out) > 0 and max(r.fan_in, r.fan_out) <= config.fan_balance * min(r.fan_in, r.fan_out)
        near_seeds = getattr(r, 'near_seed_count', 0)
        branches = getattr(r, 'seed_branch_count', 0)
        if r.is_depth4_leaf and r.sum_in > 0:
            role, score, code = 'terminal', .25, 'T_BOUNDARY'
            rule = 'depth=4, out_degree=0; направление после границы неизвестно'
        elif (r.fan_in >= config.high_fan and r.fan_out >= config.high_fan and r.volume >= threshold
              and comparable and near_seeds >= config.coordinator_near_seeds
              and branches >= config.coordinator_branches
              and (r.is_seed or ratio > config.low_ratio)):
            role, code = 'coordinator', 'C_BOTH_FANS'
            score = .65 + .15 * min(1., min(r.fan_in, r.fan_out)/(2*config.high_fan)) + .1 * min(1., r.volume/max(2*threshold, 1))
            rule = (f'Обе степени ≥{config.high_fan}, баланс ≤{config.fan_balance:g}×; '
                    f'объём ≥P{config.coordinator_quantile*100:g}={threshold:.2f} KZT; '
                    f'seed за ≤2 шага ≥{config.coordinator_near_seeds}; ветвей ≥{config.coordinator_branches}; '
                    f'не выполнено правило консолидации')
        elif not r.is_seed and r.fan_in >= config.high_fan and ratio <= config.low_ratio:
            role, code = 'consolidator', 'C_RETAIN'
            score = .6 + .15 * min(1., r.fan_in/(2*config.high_fan)) + .15 * (1-ratio/config.low_ratio)
            rule = f'Не seed; fan_in ≥{config.high_fan}; ratio ≤{config.low_ratio:g}'
        elif r.fan_out >= config.high_fan:
            # Структурная рассылка не исчезает при неполном входе или слабом временном сигнале.
            role, code = 'distributor', 'D_FAN'
            score = .45 + .2 * fan_strength + .1 * fast + .1 * strict
            rule = f'fan_out ≥{config.high_fan}; временное сопоставление влияет на score, не на наличие рассылки'
        elif not r.is_seed and 1-config.transit_tolerance <= ratio <= 1+config.transit_tolerance and comparable and fast >= config.rapid_share:
            role, code = 'transit', 'TR_BALANCED'
            score = .5 + .15 * (1-abs(ratio-1)/config.transit_tolerance) + .1 * fast + .1 * strict
            rule = f'Не seed; ratio {1-config.transit_tolerance:g}–{1+config.transit_tolerance:g}; степени ≤{config.fan_balance:g}×; FIFO за 0–2 дня ≥{config.rapid_share:.0%}'
        elif r.sum_in > 0 and r.fan_out == 0:
            role, code = 'terminal', 'T_OBSERVED'
            score = .5 + .15 * min(1., r.fan_in/config.high_fan)
            rule = 'Вход >0; выходов нет в выборке; конечный получатель не доказан'
        else:
            role, score, code = 'peripheral', .4, 'P_NO_RULE'
            rule = 'Ни одно из предшествующих правил не выполнено; отсутствие сигнала не доказывает безопасность'
        ratio_text = f'{ratio:.0%}' if np.isfinite(ratio) else 'н/д (вход=0)'
        evidence = f'Гипотеза {role}: вход от {r.fan_in}, выход к {r.fan_out}; выход/вход {ratio_text}; объём {r.volume:.0f} KZT'
        if role == 'coordinator':
            evidence += f'; seed ≤2 шага: {near_seeds}, ветвей: {branches}'
        if role in ('transit', 'distributor'):
            evidence += f'; FIFO 0–2д {fast:.0%}'
        if r.is_depth4_leaf:
            evidence += '; возможен артефакт обрыва графа на 4 колене'
        elif r.is_seed:
            evidence += '; вход seed неполон'
            score = min(score, .55)
        elif r.sum_in == 0:
            evidence += '; вход не наблюдается'
            score = min(score, .5)
        elif role == 'terminal':
            evidence += '; нет выхода в выборке'
        return role, round(float(np.clip(score, 0, 1)), 6), evidence, code, rule
    result = [classify(r) for r in df.itertuples(index=False)]
    df[['role', 'role_score', 'evidence', 'rule_code', 'rule_text']] = result
    df['role_score'] = df.role_score.astype(float)
    return df, {**asdict(config), 'coordinator_volume_p90_kzt': threshold, 'rule_version': RULE_VERSION}
