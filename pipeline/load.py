from pathlib import Path
import numpy as np
import pandas as pd


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(data_dir):
    data_dir = Path(data_dir)
    nodes, edges, tx = [pd.read_parquet(data_dir / f'{name}.parquet')
                        for name in ('nodes', 'edges', 'transactions')]
    for frame, cols in [(nodes, ['gid', 'depth', 'is_seed']),
                        (edges, ['src', 'dst', 'sum_kzt', 'n_tx', 'depth']),
                        (tx, ['src', 'dst', 'date', 'sum_kzt'])]:
        require(set(cols) <= set(frame.columns), f'Нет обязательных колонок: {cols}')
        require(not frame[cols].isna().any().any(), 'NULL во входных данных')
    for frame, cols in [(nodes, ['gid', 'depth']), (edges, ['src', 'dst', 'n_tx', 'depth']),
                        (tx, ['src', 'dst'])]:
        for col in cols:
            require(pd.api.types.is_integer_dtype(frame[col]), f'{col}: ожидается целый тип')
    require(pd.api.types.is_bool_dtype(nodes.is_seed), 'is_seed должен быть bool')
    require(not nodes.gid.duplicated().any(), 'Повтор gid')
    require(not edges.duplicated(['src', 'dst']).any(), 'Повтор агрегированной пары')
    require(nodes.depth.between(0, 4).all(), 'Глубина узла вне 0..4')
    require(edges.depth.between(1, 4).all(), 'Глубина ребра вне 1..4')
    require((nodes.is_seed == nodes.depth.eq(0)).all(), 'Seed не соответствует depth=0')
    for frame in (edges, tx):
        require(set(frame.src) | set(frame.dst) <= set(nodes.gid), 'Неизвестные концы рёбер')
        require(np.isfinite(frame.sum_kzt).all() and frame.sum_kzt.gt(0).all(), 'Некорректная сумма')
    require(edges.n_tx.gt(0).all(), 'n_tx должен быть положительным')
    require(tx.sum_kzt.ge(5000).all(), 'Транзакция ниже порога 5000')
    tx['date'] = pd.to_datetime(tx.date, errors='raise')
    require(tx.date.notna().all(), 'Пустая дата')
    require(tx.date.ge('2026-07-01').all() and tx.date.lt('2026-08-01').all(), 'Дата вне июля 2026')
    agg = tx.groupby(['src', 'dst']).agg(total=('sum_kzt', 'sum'), count=('sum_kzt', 'size')).reset_index()
    merged = edges.merge(agg, on=['src', 'dst'], how='outer', indicator=True, validate='one_to_one')
    require(merged._merge.eq('both').all(), 'Пары edges и transactions расходятся')
    require(np.allclose(merged.sum_kzt, merged.total, rtol=1e-10, atol=.01), 'Суммы edges и transactions расходятся')
    require(merged.n_tx.eq(merged['count']).all(), 'n_tx и transactions расходятся')
    return nodes.sort_values('gid').reset_index(drop=True), edges.sort_values(['src', 'dst']), tx
