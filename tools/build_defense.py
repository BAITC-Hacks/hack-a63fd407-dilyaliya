"""Generate defense notes from current metrics without hardcoded client IDs."""
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main():
    df = pd.read_parquet(ROOT / 'output/node_metrics.parquet').sort_values(
        ['priority_score', 'gid'], ascending=[False, True])
    df['rank'] = range(1, len(df) + 1)
    report = json.loads((ROOT / 'output/run_report.json').read_text(encoding='utf-8'))
    checks = [s for s in report['ranking_sensitivity'] if s['scenario'] not in ('baseline', 'without_role')]
    overlap = min(s['top_overlap'] for s in checks)
    notes = ['# Защита проекта «Граф денег»', '',
             'Актуальный пяти­минутный сценарий: [output/demo.md](../output/demo.md). '
             'Схема: [architecture.svg](architecture.svg). Запуск: `sh run.sh` (macOS/Linux), '
             '`run.bat` (Windows); полный комплект требует CPython 3.11 x64/ARM64 для поддерживаемой платформы.', '',
             f'Последний расчёт: {report["elapsed_seconds"]:.3f} с; '
             f'{report["nodes"]} узлов, {report["clusters"]} сообществ. '
             'Установка и загрузка Python не входят в этот замер.', '',
             f'При отдельных изменениях весов ±20% остаются минимум {overlap} участников топа. '
             'Отдельно измеряется устойчивость к порогам ролей. Ни один показатель не является accuracy.', '',
             '## Примеры по актуальным результатам', '']
    for role in ('distributor', 'consolidator', 'coordinator'):
        candidates = df[df.role.eq(role)]
        if candidates.empty:
            notes += [f'Роль {role}: в текущем расчёте не выявлена.', '']
            continue
        row = candidates.iloc[0]
        path = ' → '.join(row.seed_path)
        notes += [f'### {role}: gid {int(row.gid)}', '',
                  f'Место {int(row["rank"])}; при изменении весов {int(row.rank_min)}–{int(row.rank_max)}. '
                  f'При изменении порогов {int(row.threshold_rank_min)}–{int(row.threshold_rank_max)}.', '',
                  row.evidence, '', row.rule_text, '',
                  f'Путь: {path or "не наблюдается"}. Наличие рёбер не устанавливает порядок движения одной суммы.', '']
    notes += ['## Ответы на вопросы', '',
              '- Нет ground truth: проверяем контракты, границы, воспроизводимость и чувствительность, не accuracy.',
              '- 16 компонент с рёбрами плюс 19 изолятов; все узлы сохранены.',
              '- Depth4 terminal имеет score 0,25 и оговорку; накопление не доказано, бонус collection равен нулю.',
              '- Coordinator требует близких seed и входных ветвей, а не только большого оборота.',
              '- Шесть вкладов рейтинга, два набора сценариев, постоянный топ и отдельный режим пути доступны в UI.',
              '- FIFO сохраняет суммы внутри узла и сценария; не устанавливает происхождение денег.',
              '- Помощник на локальных правилах, без LLM, облака или внешних атрибутов.',
              '- Карточки и запросы дополняются аналитиком; локальная история не является защищённым аудитом.',
              '- Проверка текущей macOS не заменяет испытания других ОС. Ограничения запуска перечислены в README.', '']
    (ROOT / 'docs/defense.md').write_text('\n'.join(notes), encoding='utf-8')


if __name__ == '__main__':
    main()
