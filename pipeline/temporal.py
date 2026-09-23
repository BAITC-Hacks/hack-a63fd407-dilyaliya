"""Сопоставление наблюдаемых сумм FIFO за два календарных дня.

Два сценария порядка внутри дня, не доказательство происхождения денег.
В каждом сценарии входящая сумма расходуется не более одного раза.
"""
from collections import deque
import pandas as pd


def amount_matching(nodes, tx):
    events = {int(gid): [] for gid in nodes.gid}
    for i, r in enumerate(tx.itertuples(index=False), 1):
        day = pd.Timestamp(r.date).normalize()
        amount = int(round(float(r.sum_kzt) * 100))
        events[int(r.dst)].append((day, 'in', i, amount))
        events[int(r.src)].append((day, 'out', i, amount))
    totals, matches = {}, []
    for gid, records in events.items():
        total_out = sum(amount for _, kind, _, amount in records if kind == 'out')
        values = {}
        for scenario in ('strict', 'same_day_possible'):
            # strict: все выходы дня перед входами; same_day_possible: наоборот.
            order = {'out': 0, 'in': 1} if scenario == 'strict' else {'in': 0, 'out': 1}
            balance = deque()
            matched = 0
            for day, kind, ref, amount in sorted(records, key=lambda r: (r[0], order[r[1]], r[2])):
                while balance and (day - balance[0][0]).days > 2:
                    balance.popleft()
                if kind == 'in':
                    balance.append([day, ref, amount])
                    continue
                remaining = amount
                while remaining and balance:
                    incoming = balance[0]
                    part = min(remaining, incoming[2])
                    remaining -= part
                    incoming[2] -= part
                    matched += part
                    matches.append(dict(gid=gid, scenario=scenario, in_ref=f'row:{incoming[1]}',
                                        out_ref=f'row:{ref}', in_date=incoming[0].date().isoformat(),
                                        out_date=day.date().isoformat(), matched_kzt=part / 100,
                                        lag_days=(day-incoming[0]).days))
                    if incoming[2] == 0:
                        balance.popleft()
            values[f'fifo_{scenario}_share'] = matched / total_out if total_out else 0.
            values[f'fifo_{scenario}_kzt'] = matched / 100
        totals[gid] = values
    metrics = pd.DataFrame.from_dict(totals, orient='index').rename_axis('gid').reset_index()
    columns = ['gid', 'scenario', 'in_ref', 'out_ref', 'in_date', 'out_date', 'matched_kzt', 'lag_days']
    return metrics, pd.DataFrame(matches, columns=columns)
