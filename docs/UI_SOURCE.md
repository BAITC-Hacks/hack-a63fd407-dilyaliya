# Полные исходники обновлённого UI

Файлы приведены целиком, без сокращений и заглушек. Снимок соответствует текущему `output/graph.html`, включая тёмную тему и свечение. Сам автономный HTML со всеми данными доступен отдельным полным файлом `output/graph.html` и включён в `ui-update.zip`. Генерируемые данные не дублируются в этом документе. Код существующих `app/cases.py` и `app/cases.js` не изменён; они также включены в ZIP для полноты комплекта UI.

## app/build.py

````python
import json
import hashlib
from app.cases import case_context
import math
from pathlib import Path


def build(df, edges, destination, clusters=None, top=None, stability=None, tx=None, graph=None):
    records = json.loads(df.to_json(orient='records', date_format='iso'))
    by_gid = {r['gid']: r for r in records}
    groups = list(df.groupby('cluster_id', sort=True))
    cols = max(1, math.ceil(math.sqrt(len(groups))))
    for i, (_, group) in enumerate(groups):
        ordered = group.sort_values(['priority_score', 'gid'], ascending=[False, True])
        for j, gid in enumerate(ordered.gid):
            angle = j * math.pi * (3 - math.sqrt(5))
            radius = 9 * math.sqrt(j)
            by_gid[gid]['x'] = (i % cols) * 330 + radius * math.cos(angle)
            by_gid[gid]['y'] = (i // cols) * 330 + radius * math.sin(angle)
    cases = case_context(records, graph)
    # gid передаём строками: int64 может выходить за точность JavaScript Number.
    for r in records:
        r['gid'] = str(r['gid'])
    links = [dict(src=str(r.src), dst=str(r.dst), sum_kzt=float(r.sum_kzt), n_tx=int(r.n_tx))
             for r in edges.itertuples(index=False)]
    cluster_records = [] if clusters is None else clusters.to_dict(orient='records')
    for cluster in cluster_records:
        cluster['top_gids'] = [str(gid) for gid in json.loads(cluster['top_gids'])]
    top_records = [] if top is None else top.to_dict(orient='records')
    for row in top_records:
        row['gid'] = str(row['gid'])
    transactions = [dict(ref=f'row:{i+1}', src=str(r.src), dst=str(r.dst), date=r.date.isoformat(), sum_kzt=float(r.sum_kzt))
                    for i, r in enumerate(tx.itertuples(index=False))]
    fingerprint = hashlib.sha256(json.dumps({'nodes': [(r['gid'], r['depth'], r['is_seed']) for r in records],
                                            'edges': links, 'transactions': transactions}, sort_keys=True).encode()).hexdigest()
    payload = json.dumps({'nodes': records, 'edges': links, 'clusters': cluster_records,
                          'transactions': transactions, 'cases': cases, 'fingerprint': fingerprint,
                          'top': top_records, 'stability': stability or []},
                         ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    template = Path(__file__).with_name('template.html').read_text(encoding='utf-8')
    template = template.replace('__GRAPH_STYLE__', Path(__file__).with_name('style.css').read_text(encoding='utf-8'))
    template = template.replace('__GRAPH_SCRIPT__', Path(__file__).with_name('view.js').read_text(encoding='utf-8'))
    template = template.replace('__GRAPH_ENGINE__', Path(__file__).with_name('graph.js').read_text(encoding='utf-8'))
    template = template.replace('__CASE_JS__', Path(__file__).with_name('cases.js').read_text(encoding='utf-8'))
    Path(destination).write_text(template.replace('__GRAPH_DATA__', payload), encoding='utf-8')
````

## app/template.html

````html
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Граф денег · Рабочее место аналитика</title>
  <style>__GRAPH_STYLE__</style>
</head>
<body>
  <div class="app-header">
    <header>
      <div class="brand" aria-hidden="true">ГД</div>
      <div><h1>Граф денег</h1><p class="muted">Анализ переводов · июль 2026</p></div>
      <div id="overview" class="overview"></div>
      <span class="local-label">Локально · без облака</span>
    </header>
    <div class="toolbar">
      <form id="search" role="search">
        <div class="search-field">
          <label class="sr-only" for="gid">Поиск gid</label>
          <input id="gid" type="text" inputmode="numeric" placeholder="Найти участника по gid"
                 role="combobox" aria-autocomplete="list" aria-expanded="false"
                 aria-controls="suggestions" autocomplete="off" spellcheck="false">
          <div id="search-popup" class="search-popup" hidden>
            <ul id="suggestions" role="listbox" aria-label="Найденные участники"></ul>
            <p id="suggestion-count" class="muted"></p>
          </div>
        </div>
        <button type="submit" class="primary">Найти</button>
      </form>
      <label class="cluster-picker">Перейти к кластеру
        <select id="cluster" aria-label="Перейти к кластеру"><option value="">Обзор сети</option></select>
      </label>
      <button id="reset" type="button">Вся сеть</button>
    </div>
    <div id="announcement" class="announcement" role="status" aria-live="polite"></div>
  </div>
  <nav class="mobile-tabs" aria-label="Рабочая область">
    <button type="button" data-panel="graph" aria-pressed="true">Граф</button>
    <button type="button" data-panel="top" aria-pressed="false">Топ-30</button>
    <button type="button" data-panel="detail" aria-pressed="false">Карточка</button>
  </nav>
  <main data-panel="graph">
    <aside class="candidates" aria-label="Приоритетные узлы">
      <div class="section-title"><h2 id="top-title">Приоритетные узлы</h2><span class="badge">Топ</span></div>
      <p class="muted">Очередь ручной проверки. Нажмите на участника, чтобы увидеть его связи.</p>
      <details id="stability"><summary>Устойчивость приоритета</summary><p class="muted"></p></details>
      <div id="top"></div>
    </aside>
    <section class="graph-area" aria-label="Граф переводов">
      <div class="graph-toolbar">
        <div><h2 id="view-title">Обзор сети</h2><span id="stats" class="muted"></span></div>
        <div class="scope-controls" role="group" aria-label="Область графа">
          <label><input id="neighbors" type="checkbox" disabled>Один шаг</label>
          <label><input id="route-only" type="checkbox" disabled>Путь от seed</label>
        </div>
      </div>
      <div class="plot-row">
        <div id="stage">
          <canvas id="canvas" tabindex="0" aria-label="Граф переводов. Стрелки клавиатуры перемещают граф; плюс и минус меняют масштаб; Home показывает всё. Для выбора участника используйте поиск или топ."></canvas>
          <div id="graph-tooltip" class="graph-tooltip" role="tooltip" hidden></div>
          <div id="empty-graph" class="empty-graph" hidden><strong>Нет видимых участников</strong><p>Включите роли в легенде.</p><button id="restore-roles" type="button">Показать все роли</button></div>
        </div>
        <div class="view-controls" role="group" aria-label="Навигация по графу">
          <button id="zoom-in" type="button" aria-label="Приблизить" title="Приблизить (+)">+</button>
          <output id="zoom-level" aria-label="Масштаб">100%</output>
          <button id="zoom-out" type="button" aria-label="Отдалить" title="Отдалить (−)">−</button>
          <span class="control-divider"></span>
          <button id="fit-selection" type="button" aria-label="Уместить выбранное и его связи" title="Уместить выбранное и его связи (Fit to selection)" disabled>◎</button>
          <span class="control-caption">Фокус</span>
          <button id="fit-all" type="button" aria-label="Показать всё" title="Показать всё (Home)">⌂</button>
          <span class="control-caption">Всё</span>
        </div>
      </div>
      <div class="graph-footer">
        <p class="graph-help">Колесо / два пальца — масштаб · перетаскивание — перемещение</p>
        <p id="flow-key" class="muted" hidden><span class="incoming">→ К выбранному</span> · <span class="outgoing">→ От выбранного</span> · остальная сеть приглушена</p>
        <details id="legend-panel">
          <summary>Роли и обозначения <span id="role-count">6 из 6</span></summary>
          <div id="legend" role="group" aria-label="Видимые роли"></div>
          <p class="muted">Внешнее кольцо — seed, исходный участник. Форма дублирует цвет роли.</p>
          <p id="edge-key" class="muted"></p>
        </details>
        <details id="cluster-info"><summary id="cluster-title">О кластерах</summary><div id="cluster-summary"></div></details>
      </div>
    </section>
    <aside class="inspector" aria-label="Карточка узла">
      <div class="section-title"><h2>Карточка участника</h2><button id="export-card" type="button" disabled>Текст</button></div>
      <details id="card-preview" hidden><summary>Текст карточки готов</summary><p class="muted">Можно скопировать текст или сохранить предложенный TXT-файл.</p><textarea id="card-text" aria-label="Текст карточки" readonly></textarea></details>
      <div id="node-detail"></div>
    </aside>
  </main>
  <footer>Роли — гипотезы для проверки. Балл не означает вероятность нарушения. Граница 4-го колена может скрывать дальнейшие переводы.</footer>
  <dialog id="caseDialog" aria-labelledby="caseTitle"><div id="caseContent"></div></dialog>
  <script>const data=__GRAPH_DATA__;</script>
  <script>__GRAPH_ENGINE__</script>
  <script>__GRAPH_SCRIPT__</script>
  <script>__CASE_JS__</script>
</body>
</html>
````

## app/style.css

````css
:root {
  color-scheme: dark;
  --bg: #090f1c;
  --panel: #101929;
  --line: #26344a;
  --text: #e3ecfa;
  --muted: #9babc2;
  --focus: #76d8f0;
}
* { box-sizing: border-box; scrollbar-color: #3b506c #0d1625; }
[hidden] { display: none !important; }
body {
  margin: 0;
  height: 100vh;
  height: 100dvh;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.5 system-ui, sans-serif;
}
button, input, select, textarea { font: inherit; color: inherit; }
button, select, input:not([type=checkbox]), textarea {
  border: 1px solid #34465f;
  border-radius: 6px;
  padding: 9px 11px;
  background: var(--panel);
}
button { cursor: pointer; }
input::placeholder, textarea::placeholder { color: #899cb7; opacity: 1; }
::selection { background: #285a73; color: #f3fbff; }
button:hover:not(:disabled) { background: #20324b; border-color: #527491; }
button:disabled { opacity: .42; cursor: default; }
button:focus-visible, input:focus-visible, select:focus-visible, summary:focus-visible, canvas:focus-visible {
  outline: 3px solid #76d8f0;
  outline-offset: 2px;
}
input[type=checkbox] { accent-color: var(--focus); width: 16px; height: 16px; margin: 0; }
h1, h2, h3, p { margin: 0; }
h1 { font-size: 21px; line-height: 1.2; }
h2 { font-size: 16px; }
h3 { font-size: 15px; margin: 18px 0 10px; }
p { margin: 8px 0 12px; }
summary { cursor: pointer; padding: 8px 0; font-weight: 600; }
details > p { margin-top: 3px; }
.muted { color: var(--muted); font-size: 12px; }
.app-header { grid-row: 1; position: sticky; top: 0; z-index: 10; background: var(--panel); border-bottom: 1px solid var(--line); }
header { display: flex; gap: 12px; align-items: center; padding: 12px 20px 8px; }
header p { margin: 2px 0 0; }
.brand { background: linear-gradient(135deg, #245475, #203151); color: #eff6ff; border-radius: 8px; padding: 9px; font-size: 18px; font-weight: 700; }
.overview { display: flex; gap: 24px; margin-left: auto; }
.overview strong { font-size: 19px; font-variant-numeric: tabular-nums; margin-right: 6px; }
.overview span { color: var(--muted); font-size: 12px; }
.local-label { font-size: 11px; color: var(--muted); margin-left: 12px; }
.toolbar { display: flex; align-items: center; gap: 16px; padding: 8px 20px 12px; }
#search { display: flex; gap: 8px; flex: 1; max-width: 590px; }
.search-field { position: relative; min-width: 0; flex: 1; }
#gid { width: 100%; font-size: 15px; }
.primary { background: #195a72; color: #effaff; border-color: #438ba6; }
.primary:hover:not(:disabled) { background: #226b83; color: #f4fcff; }
.cluster-picker { display: flex; align-items: center; gap: 8px; font-size: 12px; white-space: nowrap; }
#cluster { max-width: 230px; }
.search-popup { position: absolute; top: calc(100% + 5px); left: 0; right: 0; background: var(--panel); border: 1px solid #3a5874; border-radius: 7px; box-shadow: 0 6px 18px #00000055; overflow: hidden; }
#suggestions { list-style: none; padding: 0; margin: 0; max-height: 290px; overflow: auto; }
#suggestions li { padding: 9px 12px; cursor: pointer; }
#suggestions li[aria-selected=true], #suggestions li:hover { background: #20344f; }
#suggestions strong { display: block; font-size: 14px; font-variant-numeric: tabular-nums; }
#suggestions small { color: var(--muted); }
#suggestion-count { margin: 0; padding: 7px 12px; border-top: 1px solid var(--line); }
.announcement:empty { display: none; }
.announcement { padding: 5px 20px; background: #182c43; font-size: 12px; }
.mobile-tabs { grid-row: 2; display: none; }
main { grid-row: 3; display: grid; grid-template-columns: 282px minmax(300px, 1fr) 356px; min-height: 0; }
aside { min-height: 0; overflow: auto; background: var(--panel); padding: 17px; overscroll-behavior: contain; }
.candidates { border-right: 1px solid var(--line); }
.inspector { border-left: 1px solid var(--line); }
.section-title { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.section-title button { font-size: 12px; padding: 5px 9px; }
.badge { font-size: 11px; background: #1e2c43; padding: 3px 8px; border-radius: 4px; }
#stability { border-bottom: 1px solid var(--line); margin-bottom: 12px; font-size: 12px; }
.candidate { border: 1px solid var(--line); border-radius: 7px; margin-bottom: 9px; overflow: hidden; background: var(--panel); }
.candidate[data-selected=true] { border-color: #5897b0; background: #152a3e; box-shadow: inset 3px 0 var(--focus), 0 0 14px #3c9bce16; }
.candidate-button { display: block; text-align: left; border: 0; width: 100%; padding: 11px 12px; border-radius: 0; background: transparent; }
.candidate-heading { display: flex; align-items: center; gap: 7px; }
.rank { color: var(--muted); width: 20px; flex-shrink: 0; font-size: 12px; }
.candidate-gid { font-size: 13px; font-weight: 650; font-variant-numeric: tabular-nums; }
.candidate-meta { display: flex; gap: 6px; align-items: center; margin-top: 7px; font-size: 12px; }
.candidate-score { font-size: 15px; font-weight: 700; margin-left: auto; font-variant-numeric: tabular-nums; }
.candidate details { padding: 0 12px 0 39px; font-size: 11px; color: var(--muted); }
.candidate summary { font-weight: 400; padding: 0 0 7px; }
.candidate details p { font-size: 12px; }
.role-icon { text-shadow: 0 0 9px currentColor; display: inline-block; font-size: 18px; width: 19px; text-align: center; line-height: 1; }
.graph-area { display: grid; grid-template-rows: auto minmax(180px, 1fr) auto; min-width: 0; min-height: 0; }
.graph-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 12px 14px; border-bottom: 1px solid var(--line); background: #111c2d; }
#view-title { font-size: 14px; overflow-wrap: anywhere; }
#stats { font-size: 11px; }
.scope-controls { display: flex; gap: 9px; flex-wrap: wrap; justify-content: flex-end; }
.scope-controls label { display: flex; align-items: center; gap: 5px; font-size: 11px; white-space: nowrap; }
.plot-row { display: grid; grid-template-columns: minmax(0, 1fr) 54px; min-height: 0; }
#stage { position: relative; overflow: hidden; min-height: 0; background: radial-gradient(ellipse at 48% 42%, #13253d 0%, #0c1729 48%, #070d19 100%); }
canvas { display: block; width: 100%; height: 100%; touch-action: none; cursor: grab; }
canvas:active { cursor: grabbing; }
.view-controls { display: flex; align-items: center; flex-direction: column; gap: 5px; padding: 10px 4px; background: var(--panel); border-left: 1px solid var(--line); overflow: hidden; }
.view-controls button { width: 42px; min-height: 42px; padding: 0; flex-shrink: 0; font-size: 23px; line-height: 1; }
.view-controls output { font-size: 10px; font-variant-numeric: tabular-nums; }
.control-divider { width: 26px; border-top: 1px solid var(--line); margin: 5px; }
.control-caption { font-size: 10px; color: var(--muted); margin-top: -4px; }
.graph-tooltip { position: absolute; pointer-events: none; padding: 9px 12px; color: #eff6ff; background: #172940; border-radius: 6px; font-size: 12px; max-width: 270px; box-shadow: 0 3px 10px #0008; white-space: pre-line; }
.empty-graph { position: absolute; inset: 0; display: grid; place-content: center; text-align: center; padding: 20px; }
.empty-graph button { margin: 0 auto; }
.graph-footer { border-top: 1px solid var(--line); padding: 7px 14px; background: var(--panel); max-height: 34vh; overflow: auto; }
.graph-footer p { margin: 3px 0 6px; }
.graph-help { color: var(--muted); font-size: 11px; }
.graph-footer summary { font-size: 12px; padding: 5px 0; }
#role-count { color: var(--muted); font-weight: 400; margin-left: 8px; }
#legend { display: grid; grid-template-columns: repeat(auto-fit, minmax(122px, 1fr)); gap: 4px 10px; padding: 7px 0; }
.legend-role { display: flex; align-items: center; gap: 5px; font-size: 12px; cursor: pointer; min-height: 27px; }
.legend-role small { margin-left: auto; color: var(--muted); font-size: 10px; }
.incoming { color: #fbc775; }
.outgoing { color: #69e0ff; }
#cluster-info { border-top: 1px solid var(--line); }
#cluster-summary { font-size: 12px; }
.gid-title { font-size: 19px; font-variant-numeric: tabular-nums; margin: 16px 0 8px; overflow-wrap: anywhere; }
.role-badge { display: flex; align-items: center; gap: 6px; font-weight: 600; }
.role-badge small { margin-left: auto; font-size: 11px; font-weight: 400; color: var(--muted); }
.evidence { padding-left: 12px; border-left: 3px solid #486888; font-size: 13px; margin-top: 14px; }
.metrics { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 14px 0; }
.metric { padding: 10px; background: linear-gradient(145deg, #192940, #131e31); border: 1px solid #2b3e58; border-radius: 6px; }
.metric strong { color: #edf5ff; display: block; font-size: 19px; font-variant-numeric: tabular-nums; letter-spacing: -.4px; }
.metric span { color: var(--muted); font-size: 11px; }
.notice { color: #efd9b4; padding: 10px 12px; background: #30251b; border-left: 3px solid #b28449; border-radius: 3px; font-size: 12px; }
.case-links, .nav-buttons { display: flex; gap: 7px; flex-wrap: wrap; margin: 12px 0; }
.case-links button, .nav-buttons button { font-size: 12px; flex: 1; }
.inspector details { border-top: 1px solid var(--line); margin-top: 12px; }
.inspector summary { font-size: 13px; }
.contribution { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; padding: 4px 0; }
.path-node { display: block; font-size: 12px; margin: 4px 0; max-width: 100%; }
.path-arrow { display: block; font-size: 11px; color: var(--muted); margin-left: 12px; }
.connection-filter { display: flex; gap: 5px; margin: 8px 0; flex-wrap: wrap; }
.connection-filter button { font-size: 11px; padding: 6px 8px; }
.connection-filter button[aria-pressed=true] { background: #1d3b52; border-color: #4c8ca5; }
.table-scroll { position: relative; max-height: 360px; overflow: auto; }
.connections { width: 100%; border-collapse: collapse; font-size: 12px; }
.connections th { position: sticky; top: 0; background: var(--panel); padding: 6px 0; text-align: left; border-bottom: 1px solid var(--line); }
.connections td { padding: 9px 0; border-bottom: 1px solid #22324a; vertical-align: top; }
.connections th:last-child, .connections td:last-child { text-align: right; }
.connections th button { border: 0; padding: 3px 0; font-weight: 600; font-size: 11px; }
.connections td button { color: #b3d9f3; display: block; border: 0; padding: 0; background: none; font-size: 12px; text-decoration: underline; text-underline-offset: 3px; font-variant-numeric: tabular-nums; }
.connections td strong { font-size: 14px; font-variant-numeric: tabular-nums; }
.connections td small { display: block; color: var(--muted); font-size: 10px; }
.empty { padding: 18px 0; color: var(--muted); }
#card-text { width: 100%; height: 180px; font-size: 12px; resize: vertical; }
footer { grid-row: 4; font-size: 11px; color: var(--muted); padding: 7px 20px; border-top: 1px solid var(--line); background: var(--panel); }
.sr-only { position: absolute; top: 0; left: 0; width: 1px; height: 1px; padding: 0; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; }
dialog { background: var(--panel); color: var(--text); border: 1px solid #3b5472; border-radius: 9px; width: min(1100px,96vw); max-height: 92vh; padding: 24px; }
dialog::backdrop { background: #020710bb; }
.case-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.case-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; }
#caseComment { width: 100%; min-height: 100px; }
#caseDialog label { display: block; margin: 7px 0; }
#caseDialog table { border-collapse: collapse; width: 100%; font-size: 12px; }
#caseDialog th, #caseDialog td { padding: 8px; border: 1px solid var(--line); text-align: left; overflow-wrap: anywhere; }
.scroll { max-height: 270px; overflow: auto; }
.case-actions { display: flex; gap: 8px; flex-wrap: wrap; }
@media (min-width: 1700px) {
  body { font-size: 16px; }
  main { grid-template-columns: 330px minmax(400px,1fr) 410px; }
  .candidate-gid { font-size: 15px; }
  .candidate-meta { font-size: 14px; }
  .muted { font-size: 13px; }
  .metric strong { font-size: 23px; }
  .evidence, .connections, .connections td button { font-size: 14px; }
  .connections td strong { font-size: 16px; }
}
@media (max-width: 1100px) {
  main { grid-template-columns: 230px minmax(240px,1fr) 306px; }
  aside { padding: 12px; }
  .candidate-gid { font-size: 11px; }
  .candidate details { padding-left: 12px; }
  .candidate-heading { gap: 3px; }
  .local-label, .cluster-picker { font-size: 0; }
  .cluster-picker select { font-size: 13px; max-width: 200px; }
  .graph-toolbar { flex-wrap: wrap; }
  .scope-controls { justify-content: flex-start; }
  .metric strong { font-size: 17px; }
}
@media (max-width: 850px) {
  body { grid-template-rows: auto auto minmax(0,1fr) auto; }
  header { padding: 10px 12px 6px; }
  h1 { font-size: 18px; }
  .overview, .local-label { display: none; }
  .toolbar { padding: 6px 12px 10px; flex-wrap: wrap; gap: 7px; }
  #search { flex-basis: 100%; max-width: none; }
  #gid { font-size: 16px; }
  .cluster-picker { flex: 1; }
  .cluster-picker select { width: 100%; max-width: none; }
  .mobile-tabs { display: flex; padding: 5px 12px; gap: 6px; background: var(--panel); border-bottom: 1px solid var(--line); }
  .mobile-tabs button { flex: 1; font-size: 12px; padding: 7px; }
  .mobile-tabs button[aria-pressed=true] { background: #1d3b52; border-color: #4c8ca5; }
  main { display: block; position: relative; overflow: hidden; }
  main > * { height: 100%; }
  main[data-panel=graph] > aside, main[data-panel=top] > :not(.candidates), main[data-panel=detail] > :not(.inspector) { display: none; }
  .graph-area { grid-template-rows: auto minmax(120px,1fr) auto; }
  .graph-toolbar { padding: 7px 12px; }
  .graph-footer { max-height: 28vh; padding: 5px 12px; }
  .graph-help { display: none; }
  .view-controls { gap: 3px; padding-top: 5px; }
  .view-controls button { min-height: 38px; height: 38px; }
  .control-caption { display: none; }
  .candidate-gid { font-size: 15px; }
  .metric strong { font-size: 21px; }
  aside { padding: 16px; }
  footer { font-size: 10px; padding: 5px 12px; }
  .case-grid { grid-template-columns: 1fr; }
  dialog { padding: 16px; }
}
@media (max-height: 650px) and (min-width: 851px) {
  header { padding-top: 7px; padding-bottom: 3px; }
  .graph-footer { max-height: 27vh; }
  .graph-help { display: none; }
  .control-caption, .control-divider { display: none; }
  .view-controls { padding-top: 5px; gap: 3px; }
  .view-controls button { min-height: 34px; height: 34px; }
}
@media (max-height: 700px) {
  .graph-area { grid-template-rows: auto minmax(80px,1fr) auto; }
  .plot-row { grid-template-columns: 1fr; grid-template-rows: minmax(0,1fr) 44px; }
  .view-controls { flex-direction: row; justify-content: center; gap: 10px; padding: 4px; border-left: 0; border-top: 1px solid var(--line); }
  .view-controls button { width: 38px; height: 34px; min-height: 34px; font-size: 21px; }
  .control-caption, .control-divider { display: none; }
}
@media (max-height: 700px) and (max-width: 850px) {
  header { padding: 6px 12px 4px; }
  header .brand, header p { display: none; }
  h1 { font-size: 16px; }
  .graph-footer { max-height: 22vh; }
}
````

## app/graph.js

````javascript
/* Canvas rendering and camera only. No role or ranking calculations. */
'use strict';
const GraphUI = (() => {
  const roles = {
    coordinator: {label: 'Координация', color: '#bc9cff', shape: 'diamond', icon: '◆'},
    consolidator: {label: 'Сбор средств', color: '#ff83b5', shape: 'square', icon: '■'},
    distributor: {label: 'Распределение', color: '#ffd070', shape: 'triangle', icon: '▲'},
    transit: {label: 'Транзит', color: '#7cafff', shape: 'circle', icon: '●'},
    terminal: {label: 'Получатель', color: '#53dfc6', shape: 'hexagon', icon: '⬢'},
    peripheral: {label: 'Периферия', color: '#8396b5', shape: 'cross', icon: '+'}
  };
  const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
  const limits = {min: .015, max: 8};
  const edgeKey = e => `${e.src}>${e.dst}`;

  function zoomCamera(camera, factor, anchor, destination = anchor) {
    const scale = clamp(camera.scale * factor, limits.min, limits.max);
    return {
      scale,
      x: destination.x - (anchor.x - camera.x) * scale / camera.scale,
      y: destination.y - (anchor.y - camera.y) * scale / camera.scale
    };
  }

  function fitCamera(points, width, height, center = null) {
    if (!points.length) return {scale: 1, x: width / 2, y: height / 2};
    const xs = points.map(p => p.x), ys = points.map(p => p.y);
    const cx = center ? center.x : (Math.min(...xs) + Math.max(...xs)) / 2;
    const cy = center ? center.y : (Math.min(...ys) + Math.max(...ys)) / 2;
    const spanX = 2 * Math.max(...xs.map(x => Math.abs(x - cx))) + 70;
    const spanY = 2 * Math.max(...ys.map(y => Math.abs(y - cy))) + 70;
    const scale = clamp(Math.min(Math.max(20, width - 40) / spanX,
                                 Math.max(20, height - 60) / spanY, 3), limits.min, limits.max);
    return {scale, x: width / 2 - cx * scale, y: height / 2 - cy * scale};
  }

  function edgeWidths(amounts) {
    const sorted = [...amounts].sort((a, b) => a - b);
    const cap = sorted[Math.max(0, Math.ceil(sorted.length * .95) - 1)] || 1;
    return {cap, width: amount => clamp(.6 + 2.2 * amount / cap, .6, 2.8)};
  }

  function nodeCamera(node, nearby, width, height) {
    // A distant counterparty must not turn a node selection into a zoom-out.
    // The explicit Fit action still fits every direct counterparty.
    const fitted = fitCamera(nearby, width, height, node);
    const scale = clamp(fitted.scale, .5, 1.8);
    return {scale, x: width / 2 - node.x * scale, y: height / 2 - node.y * scale};
  }

  function pairGeometry(points) {
    const [a, b] = [...points.values()];
    return {x: (a.x + b.x) / 2, y: (a.y + b.y) / 2,
            distance: Math.max(1, Math.hypot(a.x - b.x, a.y - b.y))};
  }

  /* Pure pointer state: testable without a browser, including pinch cancellation. */
  class Gesture {
    constructor() { this.points = new Map(); this.moved = false; }
    down(id, point) {
      if (!this.points.size) this.moved = false;
      this.points.set(id, {...point, startX: point.x, startY: point.y});
      if (this.points.size > 1) this.moved = true;
    }
    move(id, point, camera) {
      const old = this.points.get(id);
      if (!old) return camera;
      const before = this.points.size >= 2 ? pairGeometry(this.points) : null;
      this.points.set(id, {...old, ...point});
      if (Math.hypot(point.x - old.startX, point.y - old.startY) > 4) this.moved = true;
      if (before) {
        const after = pairGeometry(this.points);
        return zoomCamera(camera, after.distance / before.distance, before, after);
      }
      return {...camera, x: camera.x + point.x - old.x, y: camera.y + point.y - old.y};
    }
    up(id, cancelled = false) {
      const known = this.points.has(id);
      const click = known && this.points.size === 1 && !this.moved && !cancelled;
      this.points.delete(id);
      if (cancelled) this.moved = true;
      return click;
    }
  }

  class GraphView {
    constructor(canvas, dataset, callbacks) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.nodeSprites = this.createNodeSprites();
      this.nodes = dataset.nodes;
      this.map = new Map(this.nodes.map(n => [n.gid, n]));
      this.callbacks = callbacks;
      this.camera = {scale: 1, x: 0, y: 0};
      this.baseScale = 1;
      this.width = 1;
      this.height = 1;
      this.ready = false;
      this.selected = null;
      this.cluster = null;
      this.mode = 'all';
      this.enabled = new Set(Object.keys(roles));
      this.gesture = new Gesture();
      this.adjacent = new Map(this.nodes.map(n => [n.gid, new Set([n.gid])]));
      this.weightScale = edgeWidths(dataset.edges.map(e => e.sum_kzt));
      this.edges = dataset.edges.map(e => {
        this.adjacent.get(e.src).add(e.dst);
        this.adjacent.get(e.dst).add(e.src);
        return {...e, a: this.map.get(e.src), b: this.map.get(e.dst), stroke: this.weightScale.width(e.sum_kzt)};
      });
      this.groups = new Map();
      for (const n of this.nodes) {
        if (!this.groups.has(n.cluster_id)) this.groups.set(n.cluster_id, []);
        this.groups.get(n.cluster_id).push(n);
      }
      this.hulls = [...this.groups].map(([id, nodes]) => {
        const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y);
        return {id, count: nodes.length, left: Math.min(...xs) - 19, right: Math.max(...xs) + 19,
                top: Math.min(...ys) - 19, bottom: Math.max(...ys) + 19};
      });
      this.rebuild();
      this.bindEvents();
      this.observer = new ResizeObserver(() => this.resize());
      this.observer.observe(canvas.parentElement);
    }

    point(n) {
      return this.mode === 'path' && this.pathOrder.has(n.gid)
        ? {x: 0, y: this.pathOrder.get(n.gid) * 120} : n;
    }

    screen(n) {
      const p = this.point(n), c = this.camera;
      return {x: p.x * c.scale + c.x, y: p.y * c.scale + c.y};
    }

    radius(n) {
      const size = (3 + 4 * n.priority_score) * Math.sqrt(this.camera.scale);
      return clamp(size * (n.role === 'peripheral' ? .65 : 1), n.role === 'peripheral' ? 1.3 : 2, 12);
    }

    rebuild() {
      const path = this.map.get(this.selected)?.seed_path || [];
      this.pathOrder = new Map(path.map((id, i) => [id, i]));
      this.pathEdges = new Set(path.slice(1).map((gid, i) => `${path[i]}>${gid}`));
      const ego = this.adjacent.get(this.selected) || new Set();
      this.visible = this.nodes.filter(n => this.enabled.has(n.role)
        && (this.mode !== 'ego' || ego.has(n.gid))
        && (this.mode !== 'path' || this.pathOrder.has(n.gid)));
      this.ids = new Set(this.visible.map(n => n.gid));
      this.related = this.selected ? ego : new Set(this.visible.filter(n => n.cluster_id === this.cluster).map(n => n.gid));
      const shown = this.edges.filter(e => this.ids.has(e.src) && this.ids.has(e.dst)
        && (this.mode !== 'path' || this.pathEdges.has(edgeKey(e))));
      this.links = [shown.filter(e => !this.activeEdge(e)), shown.filter(e => this.activeEdge(e))];
      this.visibleGroups = new Set(this.visible.map(n => n.cluster_id));
      this.callbacks.state?.({nodes: this.visible.length, edges: shown.length});
      this.invalidate();
    }

    activeEdge(e) {
      return this.selected ? e.src === this.selected || e.dst === this.selected
        : this.cluster !== null && e.a.cluster_id === this.cluster && e.b.cluster_id === this.cluster;
    }

    select(gid) {
      this.selected = gid;
      this.cluster = null;
      this.rebuild();
      if (this.mode === 'all') {
        const node = this.map.get(gid);
        const nearby = this.visible.filter(n => n.cluster_id === node.cluster_id && this.related.has(n.gid));
        this.camera = nodeCamera(node, nearby, this.width, this.height);
        this.invalidate();
      } else this.focus();
    }

    selectCluster(id) {
      this.selected = null;
      this.cluster = id;
      this.mode = 'all';
      this.rebuild();
      this.focus();
    }

    setRoles(enabled) { this.enabled = new Set(enabled); this.rebuild(); }
    setMode(mode) { this.mode = this.selected ? mode : 'all'; this.rebuild(); this.focus(); }

    focus() {
      let nodes = this.visible, center = null;
      if (this.mode === 'all' && this.selected) {
        nodes = this.visible.filter(n => this.adjacent.get(this.selected).has(n.gid));
        center = this.map.get(this.selected);
      } else if (this.cluster !== null) {
        nodes = this.visible.filter(n => n.cluster_id === this.cluster);
      }
      if (nodes.length) this.camera = fitCamera(nodes.map(n => this.point(n)), this.width, this.height, center);
      this.invalidate();
    }

    reset() {
      this.selected = null;
      this.cluster = null;
      this.mode = 'all';
      this.rebuild();
      this.camera = fitCamera(this.visible, this.width, this.height);
      this.baseScale = this.camera.scale;
      this.invalidate();
    }

    zoom(factor, anchor = {x: this.width / 2, y: this.height / 2}) {
      this.camera = zoomCamera(this.camera, factor, anchor);
      this.invalidate();
    }

    resize() {
      const rect = this.canvas.getBoundingClientRect();
      if (rect.width < 1 || rect.height < 1) return; // Mobile tab is currently hidden.
      const oldWidth = this.width, oldHeight = this.height;
      this.width = rect.width;
      this.height = rect.height;
      this.baseScale = fitCamera(this.nodes, this.width, this.height).scale;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      this.canvas.width = Math.round(this.width * dpr);
      this.canvas.height = Math.round(this.height * dpr);
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (!this.ready) {
        this.camera = fitCamera(this.visible, this.width, this.height);
        this.ready = true;
      } else {
        // Preserve the current world center; resizing must not undo a pan or selection.
        this.camera.x += (this.width - oldWidth) / 2;
        this.camera.y += (this.height - oldHeight) / 2;
      }
      this.invalidate();
    }

    invalidate() {
      if (this.frame) return;
      this.frame = requestAnimationFrame(() => { this.frame = null; this.draw(); });
    }

    shape(shape, x, y, r, c = this.ctx) {
      c.beginPath();
      if (shape === 'circle') c.arc(x, y, r, 0, 2 * Math.PI);
      else if (shape === 'square') c.rect(x - r, y - r, r * 2, r * 2);
      else if (shape === 'cross') {
        c.moveTo(x - r, y); c.lineTo(x + r, y); c.moveTo(x, y - r); c.lineTo(x, y + r);
      } else {
        const count = shape === 'triangle' ? 3 : shape === 'diamond' ? 4 : 6;
        for (let i = 0; i < count; i++) {
          const angle = -Math.PI / 2 + i * 2 * Math.PI / count;
          const xx = x + r * Math.cos(angle), yy = y + r * Math.sin(angle);
          if (!i) c.moveTo(xx, yy); else c.lineTo(xx, yy);
        }
        c.closePath();
      }
    }

    createNodeSprites() {
      // Six small cached textures: no per-node blur or gradients during pan/zoom.
      const sprites = new Map();
      for (const [role, style] of Object.entries(roles)) {
        const sprite = this.canvas.ownerDocument.createElement('canvas');
        sprite.width = sprite.height = 112;
        const c = sprite.getContext('2d');
        const rgb = style.color.match(/\w\w/g).map(channel => parseInt(channel, 16));
        const shade = factor => `rgb(${rgb.map(channel => Math.round(channel * factor)).join(',')})`;
        const glow = c.createRadialGradient(56, 56, 10, 56, 56, 54);
        glow.addColorStop(0, style.color + '80');
        glow.addColorStop(.4, style.color + '2e');
        glow.addColorStop(1, style.color + '00');
        c.fillStyle = glow; c.fillRect(0, 0, 112, 112);
        this.shape(style.shape, 56, 56, 24, c);
        if (style.shape === 'cross') {
          c.strokeStyle = style.color; c.lineWidth = 4; c.lineCap = 'round'; c.stroke();
        } else {
          const body = c.createRadialGradient(47, 46, 1, 56, 59, 32);
          body.addColorStop(0, '#f1fbff');
          body.addColorStop(.24, style.color);
          body.addColorStop(.62, shade(.72));
          body.addColorStop(1, shade(.25));
          c.fillStyle = body; c.fill();
          c.strokeStyle = style.color + 'cc'; c.lineWidth = 1.2; c.stroke();
          c.save(); c.clip();
          const shine = c.createRadialGradient(48, 45, 0, 48, 45, 12);
          shine.addColorStop(0, '#ffffffaa'); shine.addColorStop(1, '#ffffff00');
          c.fillStyle = shine; c.fillRect(32, 32, 48, 48);
          c.restore();
        }
        sprites.set(role, sprite);
      }
      return sprites;
    }

    drawEdge(e) {
      const c = this.ctx, a = this.screen(e.a), b = this.screen(e.b);
      if ((a.x < -20 && b.x < -20) || (a.y < -20 && b.y < -20)
          || (a.x > this.width + 20 && b.x > this.width + 20)
          || (a.y > this.height + 20 && b.y > this.height + 20)) return;
      const active = this.activeEdge(e), path = this.mode === 'path';
      const focused = this.selected !== null || this.cluster !== null;
      const opacity = path || active ? .88 : focused ? .07 : .26;
      const color = path ? '#ffd070' : active && this.selected
        ? (e.dst === this.selected ? '#fbc775' : '#69e0ff') : '#68b8db';
      let angle, tip;
      if (e.src === e.dst) {
        const r = this.radius(e.a) + 6;
        c.beginPath(); c.arc(a.x + r, a.y - r, r, .4, 2 * Math.PI);
        angle = Math.PI / 2;
        tip = {x: a.x + 2 * r, y: a.y - r};
      } else {
        angle = Math.atan2(b.y - a.y, b.x - a.x);
        const start = this.radius(e.a) + 1, end = this.radius(e.b) + 2;
        if (Math.hypot(a.x - b.x, a.y - b.y) < start + end) return;
        tip = {x: b.x - Math.cos(angle) * end, y: b.y - Math.sin(angle) * end};
        c.beginPath(); c.moveTo(a.x + Math.cos(angle) * start, a.y + Math.sin(angle) * start);
        c.lineTo(tip.x, tip.y);
      }
      c.strokeStyle = color;
      if (active || path) {
        // A translucent outer stroke creates a laser halo without expensive blur.
        c.globalAlpha = opacity * .14; c.lineWidth = e.stroke + 3; c.stroke();
      }
      c.globalAlpha = opacity; c.lineWidth = e.stroke; c.stroke();
      if (active || path) {
        c.strokeStyle = '#e4faff'; c.globalAlpha = .35;
        c.lineWidth = Math.min(.65, e.stroke * .45); c.stroke();
      }
      c.globalAlpha = opacity; c.fillStyle = color;
      const size = active || path ? 6 : 3;
      c.beginPath(); c.moveTo(tip.x, tip.y);
      c.lineTo(tip.x - size * Math.cos(angle - .5), tip.y - size * Math.sin(angle - .5));
      c.lineTo(tip.x - size * Math.cos(angle + .5), tip.y - size * Math.sin(angle + .5));
      c.closePath(); c.fill();
    }

    draw() {
      const start = performance.now(), c = this.ctx, cam = this.camera;
      c.clearRect(0, 0, this.width, this.height);
      const focused = this.selected !== null || this.cluster !== null;
      if (this.mode !== 'path') {
        for (const h of this.hulls) {
          if (!this.visibleGroups.has(h.id)) continue;
          const x = h.left * cam.scale + cam.x, y = h.top * cam.scale + cam.y;
          const w = (h.right - h.left) * cam.scale, height = (h.bottom - h.top) * cam.scale;
          if (x > this.width || y > this.height || x + w < 0 || y + height < 0) continue;
          c.globalAlpha = this.cluster === h.id ? 1 : focused ? .3 : .8;
          c.fillStyle = this.cluster === h.id ? '#163044' : '#10203680';
          c.strokeStyle = this.cluster === h.id ? '#65bcd4' : '#29425e';
          c.lineWidth = this.cluster === h.id ? 1.5 : .7;
          c.beginPath(); c.roundRect(x, y, w, height, Math.min(14, w / 3, height / 3));
          c.fill(); c.stroke();
        }
      }
      for (const group of this.links) for (const e of group) this.drawEdge(e);
      // Draw the selected node last to keep its ring visible in dense communities.
      for (const n of this.visible) if (n.gid !== this.selected) this.drawNode(n, focused);
      if (this.ids.has(this.selected)) {
        const n = this.map.get(this.selected);
        this.drawNode(n, focused);
        this.drawLabel(n);
      }
      c.globalAlpha = 1;
      this.callbacks.camera?.(cam.scale / this.baseScale);
      this.canvas.dataset.renderMs = (performance.now() - start).toFixed(2);
      this.canvas.dataset.visibleNodes = String(this.visible.length);
    }

    drawNode(n, focused) {
      const c = this.ctx, p = this.screen(n), r = this.radius(n);
      if (p.x < -32 || p.y < -32 || p.x > this.width + 32 || p.y > this.height + 32) return;
      const active = this.related.has(n.gid) || this.mode === 'path';
      c.globalAlpha = n.gid === this.selected ? 1 : focused && !active ? .12 : n.role === 'peripheral' ? .46 : .95;
      const side = r * 112 / 24;
      c.drawImage(this.nodeSprites.get(n.role), p.x - side / 2, p.y - side / 2, side, side);
      if (n.is_seed || n.gid === this.selected) {
        c.beginPath(); c.arc(p.x, p.y, r + (n.gid === this.selected ? 4 : 2), 0, Math.PI * 2);
        c.lineWidth = n.gid === this.selected ? 2 : 1;
        c.strokeStyle = n.gid === this.selected ? '#a0edff' : '#bad0eb'; c.stroke();
        if (n.gid === this.selected) {
          c.globalAlpha = .22; c.lineWidth = 5; c.stroke();
        }
      }
    }

    drawLabel(n) {
      const c = this.ctx, p = this.screen(n);
      if (p.x < 0 || p.y < 0 || p.x > this.width || p.y > this.height) return;
      c.globalAlpha = 1;
      c.font = '12px system-ui';
      const width = Math.min(this.width - 12, Math.max(c.measureText(n.gid).width, c.measureText(roles[n.role].label).width) + 16);
      const x = clamp(p.x + 14, 6, Math.max(6, this.width - width - 6));
      const y = clamp(p.y - 48, 6, Math.max(6, this.height - 46));
      c.fillStyle = '#101d30f5'; c.strokeStyle = '#3f738c'; c.lineWidth = 1;
      c.beginPath(); c.roundRect(x, y, width, 40, 5); c.fill(); c.stroke();
      c.fillStyle = '#e4ecf9'; c.fillText(n.gid, x + 8, y + 16);
      c.fillStyle = '#a5bdd6'; c.fillText(roles[n.role].label, x + 8, y + 32);
    }

    hit(point) {
      let nearest = null, distance = Infinity;
      for (const n of this.visible) {
        const p = this.screen(n), d = Math.hypot(p.x - point.x, p.y - point.y);
        if (d < this.radius(n) + 5 && d < distance) { nearest = n; distance = d; }
      }
      if (nearest) return {node: nearest};
      if (this.mode === 'path') return {};
      const x = (point.x - this.camera.x) / this.camera.scale;
      const y = (point.y - this.camera.y) / this.camera.scale;
      const cluster = this.hulls.find(h => this.visibleGroups.has(h.id) && x >= h.left && x <= h.right && y >= h.top && y <= h.bottom);
      return cluster ? {cluster} : {};
    }

    bindEvents() {
      const point = e => {
        const r = this.canvas.getBoundingClientRect();
        return {x: e.clientX - r.left, y: e.clientY - r.top};
      };
      this.canvas.addEventListener('wheel', e => {
        e.preventDefault();
        const delta = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? this.height : 1);
        this.zoom(Math.exp(-clamp(delta, -500, 500) * .0015), point(e));
        this.callbacks.hover?.({}, point(e));
      }, {passive: false});
      this.canvas.addEventListener('pointerdown', e => {
        if (e.pointerType === 'mouse' && e.button !== 0) return;
        this.canvas.setPointerCapture(e.pointerId);
        this.gesture.down(e.pointerId, point(e));
        this.callbacks.hover?.({}, point(e));
      });
      this.canvas.addEventListener('pointermove', e => {
        const p = point(e);
        if (this.gesture.points.has(e.pointerId)) {
          this.camera = this.gesture.move(e.pointerId, p, this.camera);
          this.invalidate();
        } else if (e.pointerType !== 'touch') this.callbacks.hover?.(this.hit(p), p);
      });
      this.canvas.addEventListener('pointerup', e => {
        if (this.gesture.up(e.pointerId)) {
          const target = this.hit(point(e));
          if (target.node) this.callbacks.choose?.(target.node.gid);
          else if (target.cluster) this.callbacks.cluster?.(target.cluster.id);
        }
      });
      for (const event of ['pointercancel', 'lostpointercapture']) {
        this.canvas.addEventListener(event, e => this.gesture.up(e.pointerId, true));
      }
      this.canvas.addEventListener('pointerleave', () => this.callbacks.hover?.({}, {x: 0, y: 0}));
      this.canvas.addEventListener('keydown', e => {
        if (e.key === '+' || e.key === '=') this.zoom(1.3);
        else if (e.key === '-') this.zoom(1 / 1.3);
        else if (e.key === 'Home') this.callbacks.reset?.();
        else if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) {
          const shift = 50;
          this.camera.x += e.key === 'ArrowLeft' ? shift : e.key === 'ArrowRight' ? -shift : 0;
          this.camera.y += e.key === 'ArrowUp' ? shift : e.key === 'ArrowDown' ? -shift : 0;
          this.invalidate();
        } else return;
        e.preventDefault();
      });
    }
  }
  return {roles, limits, clamp, zoomCamera, fitCamera, nodeCamera, edgeWidths, Gesture, GraphView};
})();
if (typeof module !== 'undefined' && module.exports) module.exports = GraphUI;
````

## app/view.js

````javascript
/* Application UI. Global helpers remain compatible with the existing cases.js. */
'use strict';
const $ = id => document.getElementById(id);
const map = new Map(data.nodes.map(n => [n.gid, n]));
const clusters = new Map(data.clusters.map(c => [c.cluster_id, c]));
const topMap = new Map(data.top.map(n => [n.gid, n]));
const fmt = value => Number(value).toLocaleString('ru-RU', {maximumFractionDigits: 0});
const roles = GraphUI.roles;
const enabledRoles = new Set(Object.keys(roles));
const adjacency = new Map(data.nodes.map(n => [n.gid, []]));
for (const e of data.edges) {
  adjacency.get(e.src).push(e);
  if (e.src !== e.dst) adjacency.get(e.dst).push(e);
}
let selected = null;
let selectedCluster = null;
let connectionDirection = 'all';
let descending = true;
let suggestions = [];
let activeSuggestion = -1;
const priorityNodes = [...data.nodes].sort((a, b) => b.priority_score - a.priority_score || a.gid.localeCompare(b.gid));

function addText(parent, tag, text, className) {
  const element = document.createElement(tag);
  element.textContent = text;
  if (className) element.className = className;
  parent.append(element);
  return element;
}

function announce(text = '') { $('announcement').textContent = text; }

function roleIcon(parent, role) {
  const icon = addText(parent, 'span', roles[role].icon, 'role-icon');
  icon.style.color = roles[role].color;
  icon.setAttribute('aria-hidden', 'true');
}

function details(parent, title) {
  const block = addText(parent, 'details', '');
  addText(block, 'summary', title);
  return block;
}

function switchPanel(panel) {
  document.querySelector('main').dataset.panel = panel;
  for (const button of document.querySelectorAll('.mobile-tabs button')) {
    button.setAttribute('aria-pressed', String(button.dataset.panel === panel));
  }
  if (panel === 'graph') graph.resize();
}

for (const button of document.querySelectorAll('.mobile-tabs button')) {
  button.onclick = () => switchPanel(button.dataset.panel);
}
document.querySelector('.mobile-tabs [data-panel=top]').textContent = `Топ-${data.top.length}`;

for (const [value, title] of [[data.nodes.length, 'участников'], [data.edges.length, 'связей'], [data.clusters.length, 'кластеров']]) {
  const box = addText($('overview'), 'div', '');
  addText(box, 'strong', fmt(value));
  addText(box, 'span', title);
}
for (const cluster of data.clusters) {
  const option = addText($('cluster'), 'option', `№ ${cluster.cluster_id} · ${cluster.n_nodes} участников`);
  option.value = cluster.cluster_id;
}
for (const [role, style] of Object.entries(roles)) {
  const label = addText($('legend'), 'label', '', 'legend-role');
  label.title = role;
  const input = document.createElement('input');
  input.type = 'checkbox'; input.checked = true; input.value = role;
  input.setAttribute('aria-label', `Показывать: ${style.label}`);
  label.append(input);
  roleIcon(label, role);
  addText(label, 'span', style.label);
  addText(label, 'small', fmt(data.nodes.filter(n => n.role === role).length));
  input.onchange = () => {
    if (input.checked) enabledRoles.add(role); else enabledRoles.delete(role);
    applyRoles();
    announce(selected && !enabledRoles.has(map.get(selected).role)
      ? 'Выбранный участник скрыт фильтром. Карточка сохранена; кнопка «Фокус» вернёт его на граф.' : '');
  };
}

$('top-title').textContent = `Приоритетные узлы · ${data.top.length}`;
const perturbations = data.stability.filter(s => s.scenario !== 'baseline' && s.scenario !== 'without_role');
if (perturbations.length) {
  $('stability').querySelector('p').textContent = `При изменении отдельных весов ±20% остаются минимум ${Math.min(...perturbations.map(s => s.top_overlap))} из ${data.top.length} участников топа. Это устойчивость списка, не точность ролей.`;
} else $('stability').hidden = true;
for (const row of data.top) {
  const item = addText($('top'), 'article', '', 'candidate');
  item.dataset.gid = row.gid;
  const button = addText(item, 'button', '', 'candidate-button');
  button.type = 'button';
  button.setAttribute('aria-label', `${row.rank}. ${row.gid}. ${roles[row.role].label}. Приоритет ${row.priority_score.toFixed(3)}`);
  button.setAttribute('aria-pressed', 'false');
  const heading = addText(button, 'span', '', 'candidate-heading');
  addText(heading, 'span', String(row.rank).padStart(2, '0'), 'rank');
  addText(heading, 'span', row.gid, 'candidate-gid');
  const meta = addText(button, 'span', '', 'candidate-meta');
  roleIcon(meta, row.role);
  addText(meta, 'span', roles[row.role].label);
  addText(meta, 'span', row.priority_score.toFixed(3), 'candidate-score');
  button.onclick = () => choose(row.gid);
  addText(details(item, 'Почему в списке'), 'p', row.why);
}

function updateSelection() {
  for (const item of $('top').children) {
    const active = item.dataset.gid === selected;
    item.dataset.selected = String(active);
    item.querySelector('button').setAttribute('aria-pressed', String(active));
  }
  $('fit-selection').disabled = selected === null && selectedCluster === null;
  $('neighbors').disabled = selected === null;
  $('route-only').disabled = selected === null || !map.get(selected)?.seed_path?.length;
  $('export-card').disabled = selected === null;
  $('flow-key').hidden = selected === null;
  $('view-title').textContent = selected ? `Связи участника · ${selected}`
    : selectedCluster !== null ? `Кластер ${selectedCluster}` : 'Обзор сети';
}

function applyRoles() {
  for (const input of $('legend').querySelectorAll('input')) input.checked = enabledRoles.has(input.value);
  $('role-count').textContent = `${enabledRoles.size} из 6`;
  graph.setRoles(enabledRoles);
}

function revealSelection(includePath = false) {
  const ids = includePath ? map.get(selected)?.seed_path || [] : selected ? [selected] : [];
  for (const gid of ids) enabledRoles.add(map.get(gid).role);
  applyRoles();
}

function renderCluster() {
  const id = selectedCluster ?? map.get(selected)?.cluster_id;
  const c = clusters.get(id), box = $('cluster-summary');
  box.replaceChildren();
  if (!c) {
    $('cluster-title').textContent = 'О кластерах';
    addText(box, 'p', 'Светлый контур объединяет участников одного кластера. Наведите на область или выберите кластер в списке. Раскладка условная: расстояния на экране не измеряют финансовую близость.');
    return;
  }
  $('cluster-title').textContent = `Кластер ${c.cluster_id} · ${c.n_nodes} участников · ${c.n_seed} seed`;
  addText(box, 'p', c.hypothesis);
  if (selectedCluster !== null) $('cluster-info').open = true;
}

function emptyDetail() {
  const d = $('node-detail');
  d.replaceChildren();
  addText(d, 'h3', 'Выберите участника');
  addText(d, 'p', 'Начните с топ-листа или введите часть gid в поиске. Здесь появятся основания роли, суммы и контрагенты.', 'empty');
  addText(d, 'p', 'В графе цвет и форма обозначают роль. Больший размер — более высокий приоритет проверки.', 'muted');
}

function chooseCluster(id) {
  selected = null;
  selectedCluster = id;
  $('cluster').value = id === null ? '' : String(id);
  $('neighbors').checked = false; $('route-only').checked = false;
  $('gid').value = ''; $('card-preview').hidden = true;
  hideSuggestions(); announce(); updateSelection(); renderCluster();
  switchPanel('graph');
  if (id === null) { emptyDetail(); graph.reset(); }
  else {
    const c = clusters.get(id), d = $('node-detail');
    d.replaceChildren();
    addText(d, 'h3', `Кластер ${id}`);
    addText(d, 'p', `${c.n_nodes} участников · ${c.n_seed} seed · ${fmt(c.sum_kzt_internal)} KZT внутри группы`);
    addText(d, 'p', c.hypothesis);
    addText(d, 'h3', 'Приоритетные участники кластера');
    for (const gid of c.top_gids) {
      const n = map.get(gid);
      const b = addText(d, 'button', `${gid} · ${roles[n.role].label}`, 'path-node');
      b.onclick = () => choose(gid);
    }
    const members = data.nodes.filter(n => n.cluster_id === id);
    if (!members.some(n => enabledRoles.has(n.role))) {
      for (const n of members) enabledRoles.add(n.role);
      applyRoles(); announce('Роли этого кластера включены, чтобы его участники были видны.');
    }
    graph.selectCluster(id);
  }
}

function choose(gid) {
  const n = map.get(gid);
  if (!n) { announce('Участник с таким gid не найден. Проверьте номер или выберите подсказку.'); return; }
  const wasHidden = !enabledRoles.has(n.role);
  selected = gid; selectedCluster = null;
  $('gid').value = gid; $('cluster').value = ''; $('card-preview').hidden = true;
  hideSuggestions();
  announce(wasHidden ? `Роль «${roles[n.role].label}» включена для выбранного участника.` : '');
  connectionDirection = 'all'; descending = true;
  revealSelection($('route-only').checked);
  if (!n.seed_path?.length) $('route-only').checked = false;
  graph.mode = $('route-only').checked ? 'path' : $('neighbors').checked ? 'ego' : 'all';
  updateSelection(); renderCluster(); renderDetail(n);
  switchPanel('graph');
  graph.select(gid);
}

function renderDetail(n) {
  const d = $('node-detail');
  d.replaceChildren(); d.parentElement.scrollTop = 0;
  addText(d, 'h3', n.gid, 'gid-title');
  const badge = addText(d, 'div', '', 'role-badge');
  roleIcon(badge, n.role); addText(badge, 'span', roles[n.role].label); addText(badge, 'small', n.role);
  const metrics = addText(d, 'div', '', 'metrics');
  for (const [value, title] of [
    [n.priority_score.toFixed(4), 'Приоритет проверки'], [n.role_score.toFixed(2), 'Сила правила роли'],
    [fmt(n.sum_in), 'Вход · KZT'], [fmt(n.sum_out), 'Выход · KZT'],
    [fmt(n.fan_in), 'Плательщиков'], [fmt(n.fan_out), 'Получателей']
  ]) {
    const box = addText(metrics, 'div', '', 'metric');
    addText(box, 'strong', value); addText(box, 'span', title);
  }
  addText(d, 'p', `Кластер ${n.cluster_id} · глубина ${n.depth} · ${n.is_seed ? 'исходный участник (seed)' : 'участник цепочки'}`, 'muted');
  addText(d, 'p', n.evidence, 'evidence');
  if (n.is_depth4_leaf || n.is_seed || n.zero_sum_in) {
    addText(d, 'p', n.is_depth4_leaf
      ? 'Граница 4-го колена. Дальнейшие переводы не наблюдаются; оседание средств не установлено.'
      : n.is_seed ? 'Вход seed неполон. Отношение выхода ко входу ненадёжно.'
      : 'Вход не наблюдается. Источник средств по выборке неизвестен.', 'notice');
  }
  const actions = addText(d, 'div', '', 'case-links');
  const open = addText(actions, 'button', 'Открыть карточку дела');
  open.id = 'openCase'; open.onclick = () => openCase(n.gid);
  const request = addText(actions, 'button', 'Каких данных не хватает?');
  request.id = 'openRequests';
  request.onclick = () => { openCase(n.gid); $('requestsSection').scrollIntoView({block: 'start'}); };
  const nav = addText(d, 'div', '', 'nav-buttons');
  const index = data.top.findIndex(row => row.gid === n.gid);
  for (const [label, next] of [['← Предыдущий', index - 1], ['Следующий →', index + 1]]) {
    const button = addText(nav, 'button', label);
    button.disabled = index < 0 || next < 0 || next >= data.top.length;
    button.onclick = () => choose(data.top[next].gid);
  }
  const transfers = addText(d, 'section', ''); transfers.id = 'connections';
  renderConnections();
  const priority = details(d, 'Почему такой приоритет');
  if (topMap.has(n.gid)) addText(priority, 'p', topMap.get(n.gid).why, 'muted');
  for (const [key, title] of [['role', 'Роль'], ['volume', 'Оборот'], ['fan', 'Связи'], ['seed', 'Близость seed'], ['context', 'Охват seed'], ['collection', 'Сбор с малой отдачей']]) {
    const line = addText(priority, 'div', '', 'contribution');
    addText(line, 'span', title); addText(line, 'strong', n[`priority_${key}`].toFixed(4));
  }
  addText(priority, 'p', `Диапазон мест при разных весах: ${n.rank_min}–${n.rank_max}. Seed в пределах 2 / 4 шагов: ${n.near_seed_count} / ${n.reachable_seed_count}. Входных ветвей от seed: ${n.seed_branch_count}.`, 'muted');
  const pathBlock = details(d, 'Путь от seed'); pathBlock.id = 'path-detail';
  pathBlock.open = $('route-only').checked;
  const path = n.seed_path || [];
  if (!path.length) addText(pathBlock, 'p', 'Направленный путь от seed в выборке отсутствует.', 'muted');
  for (let i = 0; i < path.length; i++) {
    if (i) {
      const edge = adjacency.get(path[i - 1]).find(e => e.src === path[i - 1] && e.dst === path[i]);
      addText(pathBlock, 'span', `↓ ${fmt(edge.sum_kzt)} KZT · операций: ${edge.n_tx}`, 'path-arrow');
    }
    const b = addText(pathBlock, 'button', path[i] + (i === 0 ? ' · seed' : ''), 'path-node');
    b.onclick = () => choose(path[i]);
  }
  if (path.length) {
    const b = addText(pathBlock, 'button', 'Показать только этот путь');
    b.onclick = () => { $('route-only').checked = true; changeScope('path'); switchPanel('graph'); };
  }
  addText(pathBlock, 'p', 'Кратчайший направленный путь по месячному графу. Он не подтверждает перенос одной суммы и порядок переводов во времени.', 'muted');
  const time = details(d, 'Время и полнота данных');
  addText(time, 'p', `Окно активности: ${n.activity_span_hours ?? 'нет'} ч. Исходящая сумма рядом с входом ≤24ч: ${(100 * n.rapid_out_share).toFixed(1)}%.`);
  addText(time, 'p', 'Даты точны до дня. Для проверки нужны полные выписки, точное время, начальные остатки и назначения платежей.', 'muted');
}

function renderConnections() {
  const box = $('connections');
  box.replaceChildren();
  const all = adjacency.get(selected) || [];
  addText(box, 'h3', `Переводы · ${all.length} связей`);
  if (!all.length) { addText(box, 'p', 'Участник изолирован: в выгрузке нет переводов.', 'muted'); return; }
  const toolbar = addText(box, 'div', '', 'connection-filter');
  for (const [value, label] of [['all', 'Все'], ['in', 'Входящие'], ['out', 'Исходящие']]) {
    const count = all.filter(e => value === 'all' || (value === 'in' ? e.dst === selected : e.src === selected)).length;
    const button = addText(toolbar, 'button', `${label} · ${count}`);
    button.setAttribute('aria-pressed', String(connectionDirection === value));
    button.onclick = () => { connectionDirection = value; renderConnections(); };
  }
  const rows = all.filter(e => connectionDirection === 'all' || (connectionDirection === 'in' ? e.dst === selected : e.src === selected))
    .sort((a, b) => (descending ? b.sum_kzt - a.sum_kzt : a.sum_kzt - b.sum_kzt) || a.src.localeCompare(b.src) || a.dst.localeCompare(b.dst));
  const scroll = addText(box, 'div', '', 'table-scroll');
  const table = addText(scroll, 'table', '', 'connections');
  const caption = addText(table, 'caption', 'Контрагенты и агрегированные суммы переводов', 'sr-only');
  caption.id = 'connection-caption';
  const header = addText(addText(table, 'thead', ''), 'tr', '');
  addText(header, 'th', 'Участник').scope = 'col';
  const amount = addText(header, 'th', ''); amount.scope = 'col';
  amount.setAttribute('aria-sort', descending ? 'descending' : 'ascending');
  const sort = addText(amount, 'button', `Сумма KZT ${descending ? '↓' : '↑'}`);
  sort.setAttribute('aria-label', `Сортировать по сумме ${descending ? 'по возрастанию' : 'по убыванию'}`);
  sort.onclick = () => { descending = !descending; renderConnections(); };
  const body = addText(table, 'tbody', '');
  for (const e of rows) {
    const row = addText(body, 'tr', '');
    row.dataset.amount = String(e.sum_kzt);
    const person = addText(row, 'td', '');
    const self = e.src === selected && e.dst === selected, incoming = e.dst === selected;
    addText(person, 'small', self ? '↺ Самоперевод' : incoming ? '→ Входящий' : '← Исходящий');
    const gid = incoming ? e.src : e.dst;
    const button = addText(person, 'button', gid);
    button.onclick = () => choose(gid);
    const sum = addText(row, 'td', '');
    addText(sum, 'strong', fmt(e.sum_kzt));
    addText(sum, 'small', `операций: ${e.n_tx}`);
  }
  if (!rows.length) addText(box, 'p', 'В этом направлении переводов нет.', 'muted');
}

function hideSuggestions() {
  $('search-popup').hidden = true;
  $('gid').setAttribute('aria-expanded', 'false');
  $('gid').removeAttribute('aria-activedescendant');
  activeSuggestion = -1;
}

function setSuggestion(index) {
  activeSuggestion = index;
  for (const [i, option] of [...$('suggestions').children].entries()) {
    option.setAttribute('aria-selected', String(i === index));
    if (i === index) {
      $('gid').setAttribute('aria-activedescendant', option.id);
      option.scrollIntoView({block: 'nearest'});
    }
  }
}

function searchSuggestions() {
  const query = $('gid').value.trim();
  announce();
  if (query.length < 3) { hideSuggestions(); return; }
  const matches = priorityNodes.filter(n => n.gid.includes(query));
  suggestions = matches.slice(0, 8);
  activeSuggestion = -1;
  $('suggestions').replaceChildren();
  for (const [i, n] of suggestions.entries()) {
    const option = addText($('suggestions'), 'li', '');
    option.id = `suggestion-${i}`;
    option.setAttribute('role', 'option'); option.setAttribute('aria-selected', 'false');
    addText(option, 'strong', n.gid);
    addText(option, 'small', `${roles[n.role].label} · кластер ${n.cluster_id} · приоритет ${n.priority_score.toFixed(3)}`);
    option.onpointerdown = e => e.preventDefault();
    option.onclick = () => choose(n.gid);
  }
  $('suggestion-count').textContent = matches.length ? `Показано ${suggestions.length} из ${matches.length}. Уточните gid или выберите участника.` : 'Совпадений нет. Проверьте gid.';
  $('search-popup').hidden = false;
  $('gid').setAttribute('aria-expanded', 'true');
  $('gid').removeAttribute('aria-activedescendant');
}

function changeScope(mode) {
  $('neighbors').checked = mode === 'ego';
  $('route-only').checked = mode === 'path';
  if (mode === 'path') revealSelection(true);
  graph.setMode(mode);
  const block = $('path-detail');
  if (block && mode === 'path') block.open = true;
}

function resetView() {
  selected = null; selectedCluster = null;
  $('gid').value = ''; $('cluster').value = ''; $('neighbors').checked = false; $('route-only').checked = false;
  $('card-preview').hidden = true; $('cluster-info').open = false;
  for (const role of Object.keys(roles)) enabledRoles.add(role);
  hideSuggestions(); announce(); applyRoles(); graph.reset();
  updateSelection(); emptyDetail(); renderCluster(); switchPanel('graph');
}

const graph = new GraphUI.GraphView($('canvas'), data, {
  choose,
  cluster: chooseCluster,
  reset: resetView,
  state: state => {
    $('stats').textContent = `${fmt(state.nodes)} из ${fmt(data.nodes.length)} участников · ${fmt(state.edges)} связей`;
    $('empty-graph').hidden = state.nodes !== 0;
  },
  camera: scale => { $('zoom-level').textContent = `${Math.round(scale * 100)}%`; },
  hover: (hit, point) => {
    const tooltip = $('graph-tooltip');
    if (!hit.node && !hit.cluster) { tooltip.hidden = true; return; }
    tooltip.textContent = hit.node
      ? `${hit.node.gid}\n${roles[hit.node.role].label} · кластер ${hit.node.cluster_id}\nПриоритет ${hit.node.priority_score.toFixed(4)}`
      : `Кластер ${hit.cluster.id} · ${hit.cluster.count} участников\nНажмите, чтобы приблизить`;
    tooltip.hidden = false;
    const stage = $('stage').getBoundingClientRect();
    tooltip.style.left = `${GraphUI.clamp(point.x + 14, 5, Math.max(5, stage.width - tooltip.offsetWidth - 5))}px`;
    tooltip.style.top = `${GraphUI.clamp(point.y + 14, 5, Math.max(5, stage.height - tooltip.offsetHeight - 5))}px`;
  }
});
$('edge-key').textContent = `Толщина — сумма перевода: 0,6–2,8 px, верхний предел от ${fmt(graph.weightScale.cap)} KZT (95-й перцентиль). Точные суммы — в карточке.`;
$('zoom-in').onclick = () => graph.zoom(1.3);
$('zoom-out').onclick = () => graph.zoom(1 / 1.3);
$('fit-selection').onclick = () => { revealSelection($('route-only').checked); graph.focus(); announce(); };
$('fit-all').onclick = resetView;
$('reset').onclick = resetView;
$('restore-roles').onclick = () => { for (const role of Object.keys(roles)) enabledRoles.add(role); applyRoles(); graph.focus(); };
$('cluster').onchange = () => chooseCluster($('cluster').value === '' ? null : Number($('cluster').value));
$('neighbors').onchange = () => changeScope($('neighbors').checked ? 'ego' : 'all');
$('route-only').onchange = () => changeScope($('route-only').checked ? 'path' : 'all');
$('search').onsubmit = e => { e.preventDefault(); choose($('gid').value.trim()); };
$('gid').oninput = searchSuggestions;
$('gid').onfocus = () => { if ($('gid').value.trim() !== selected) searchSuggestions(); };
$('gid').onkeydown = e => {
  if (e.key === 'Escape') { hideSuggestions(); return; }
  if ($('search-popup').hidden || !suggestions.length) return;
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    setSuggestion((activeSuggestion + (e.key === 'ArrowDown' ? 1 : -1) + suggestions.length) % suggestions.length);
  } else if (e.key === 'Enter' && activeSuggestion >= 0) {
    e.preventDefault(); choose(suggestions[activeSuggestion].gid);
  }
};
document.addEventListener('pointerdown', e => { if (!$('search').contains(e.target)) hideSuggestions(); });
document.addEventListener('focusin', e => { if (!$('search').contains(e.target)) hideSuggestions(); });
$('export-card').onclick = () => {
  if (!selected) return;
  const n = map.get(selected), lines = [n.gid, n.evidence, `Кластер ${n.cluster_id}; приоритет ${n.priority_score.toFixed(4)}`,
    `Вход ${fmt(n.sum_in)} KZT; выход ${fmt(n.sum_out)} KZT`,
    ...adjacency.get(selected).map(e => `${e.src} → ${e.dst}: ${fmt(e.sum_kzt)} KZT, операций: ${e.n_tx}`),
    clusters.get(n.cluster_id).hypothesis, 'Гипотеза для ручной проверки, не утверждение о виновности.'];
  const text = lines.join('\n');
  $('card-text').value = text; $('card-preview').hidden = false; $('card-preview').open = true;
  const a = document.createElement('a');
  a.href = 'data:text/plain;charset=utf-8,' + encodeURIComponent(text);
  a.download = `node-${selected}.txt`; document.body.append(a); a.click(); a.remove();
};
emptyDetail(); renderCluster(); updateSelection();
````

## tests/test_graph_ui.cjs

````javascript
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {zoomCamera, fitCamera, nodeCamera, edgeWidths, Gesture, limits} = require('../app/graph.js');

const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-8, `${actual} != ${expected}`);
const worldAt = (camera, point) => ({x: (point.x - camera.x) / camera.scale, y: (point.y - camera.y) / camera.scale});

test('wheel zoom preserves the world point under the cursor, including both limits', () => {
  const camera = {scale: .4, x: -230, y: 18}, anchor = {x: 370, y: 125};
  const before = worldAt(camera, anchor);
  for (const factor of [1.3, .2, 1e9, 1e-9]) {
    const next = zoomCamera(camera, factor, anchor);
    const after = worldAt(next, anchor);
    close(after.x, before.x); close(after.y, before.y);
    assert.ok(next.scale >= limits.min && next.scale <= limits.max);
  }
});

test('fit contains distant neighbors and centers the selected node', () => {
  const points = [{x: -1200, y: 300}, {x: 700, y: -1800}, {x: 200, y: 100}];
  const center = points[2], width = 680, height = 430;
  const camera = fitCamera(points, width, height, center);
  close(center.x * camera.scale + camera.x, width / 2);
  close(center.y * camera.scale + camera.y, height / 2);
  for (const point of points) {
    const x = point.x * camera.scale + camera.x, y = point.y * camera.scale + camera.y;
    assert.ok(x >= 20 && x <= width - 20);
    assert.ok(y >= 30 && y <= height - 30);
  }
});

test('isolated node and empty graph have finite useful cameras', () => {
  for (const points of [[], [{x: 3300, y: 2970}]]) {
    const camera = fitCamera(points, 390, 280);
    assert.ok(Object.values(camera).every(Number.isFinite));
    assert.ok(camera.scale > 0 && camera.scale <= limits.max);
  }
});

test('automatic node selection stays close even when a counterparty is far away', () => {
  const node = {x: 1000, y: 660};
  const camera = nodeCamera(node, [node, {x: -9000, y: 10000}], 600, 400);
  assert.ok(camera.scale >= .5);
  close(camera.x + node.x * camera.scale, 300);
  close(camera.y + node.y * camera.scale, 200);
});

test('edge widths preserve order but cap outliers without changing amounts', () => {
  const amounts = Array.from({length: 99}, (_, i) => (i + 1) * 5000).concat(1e10);
  const original = [...amounts];
  const {cap, width} = edgeWidths(amounts);
  assert.equal(cap, 475000);
  assert.equal(width(0), .6); assert.equal(width(1e10), 2.8);
  assert.ok(width(10000) < width(20000));
  assert.ok(amounts.every(amount => width(amount) >= .6 && width(amount) <= 2.8));
  assert.deepEqual(amounts, original);
  assert.ok(Number.isFinite(edgeWidths([]).width(0)));
});

test('drag translates the camera and cannot select a node when released', () => {
  const gesture = new Gesture(), camera = {scale: .3, x: 20, y: 40};
  gesture.down(1, {x: 100, y: 80});
  const next = gesture.move(1, {x: 155, y: 50}, camera);
  assert.deepEqual(next, {scale: .3, x: 75, y: 10});
  assert.equal(gesture.up(1), false);
});

test('pinch zoom preserves the world point under the moving two-finger midpoint', () => {
  const gesture = new Gesture();
  const camera = {scale: .2, x: 10, y: 20};
  gesture.down(1, {x: 100, y: 100}); gesture.down(2, {x: 200, y: 100});
  const before = worldAt(camera, {x: 150, y: 100});
  const next = gesture.move(2, {x: 300, y: 140}, camera);
  const after = worldAt(next, {x: 200, y: 120});
  close(after.x, before.x); close(after.y, before.y);
  close(next.scale, .2 * Math.hypot(200, 40) / 100);
  assert.equal(gesture.up(2), false); assert.equal(gesture.up(1), false);
});

test('pointer cancellation never clicks, while the next independent tap does', () => {
  const gesture = new Gesture();
  gesture.down(1, {x: 0, y: 0});
  assert.equal(gesture.up(1, true), false);
  assert.equal(gesture.up(1), false);
  gesture.down(2, {x: 12, y: 15});
  assert.equal(gesture.up(2), true);
});
````

## README.md

````markdown
# Граф денег

Локальное рабочее место AML-аналитика: от трёх Parquet-файлов до объяснимых ролей, сообществ, приоритетов и автономного графа. Результат помогает выбрать узлы для ручной проверки. Роли — исследовательские гипотезы, а не утверждения о виновности.

## Запуск одной командой

**Windows, PowerShell или CMD:**

```powershell
.\run.bat
```

Нужен Python 3.12 x64 с launcher `py` либо уже настроенный `.venv`. При Python без launcher: `python run.py`. Скрипт создаёт окружение, устанавливает недостающие зависимости **только из локальной папки `wheelhouse`**, пересчитывает данные и создаёт `output/graph.html`. Откройте этот HTML двойным щелчком; сервер и интернет не нужны. Для запуска с другим каталогом: `.\run.bat --data data --out output --top 30`.

**Linux/macOS:** `sh run.sh` при Python 3.11–3.13. Для чистого офлайн-запуска заранее подготовьте wheels именно для ОС, архитектуры и версии Python машины жюри. Windows wheels на Linux не работают.

### Комплект без интернета

В локальной рабочей папке подготовлены `wheelhouse/` и `hackalem-offline-win-py312.zip` для **Windows x64 / CPython 3.12**. Архив содержит исходники, данные, результаты, документацию, wheels и `SHA256SUMS.json`. Python должен быть установлен заранее; его установщик в архив не включён. Локальный `.venv` не переносится: он содержит абсолютные пути и создаётся заново. Wheelhouse и ZIP исключены из Git из-за размера; для сдачи без интернета передавайте ZIP вместе с репозиторием.

Для подготовки комплекта на другой платформе, **до отключения интернета**:

```text
python -m pip download --only-binary=:all: --dest wheelhouse -r requirements.txt
python tools/package_offline.py
```

Название упаковочного скрипта/архива ориентировано на подготовленный Windows-комплект; при иной платформе назовите архив соответственно. Запуск `python run.py --online` явно разрешает первичную установку из PyPI; это подготовительный режим, он не нужен при локальных wheels. Обычный запуск не обращается в сеть и не пытается скачать пакеты при отсутствии офлайн-комплекта.

## Демо и схема решения

- [Схема решения на одном слайде](docs/architecture.svg).
- [Сценарий защиты на пять минут и три узла](docs/defense.md).
- [Результаты проверки и изменения](docs/verification.md).

![Данные → метрики → роли → интерфейс](docs/architecture.svg)

## Сценарий аналитика

На широком экране одновременно видны топ-30 слева, граф в центре и карточка справа. На телефоне они переключаются вкладками без потери выбранного узла. Поиск всегда доступен сверху: принимает полный gid и предлагает до восьми совпадений по фрагменту от трёх символов. Подсказки выбираются мышью либо стрелками и Enter. Gid хранится строкой, чтобы не потерять точность int64. В карточке: роль, сила правила, evidence, кластер, приоритет, суммы и полный список входящих/исходящих связей с сортировкой по сумме. Кнопки «Предыдущий» и «Следующий» позволяют последовательно проверить топ.

В карточке есть кратчайший направленный путь от seed с суммами рёбер и кнопкой просмотра только пути. Это путь по месячному агрегированному графу, **не доказанная последовательность перемещения одних и тех же денег**. Для seed путь состоит из самого seed; для недостижимого узла честно показывается отсутствие пути.

Выбор участника центрирует и приближает его: прямые связи выделены, остальные приглушены. Кнопка «Фокус» вмещает выбранный узел и всех видимых прямых контрагентов, включая удалённые кластеры; поэтому может уменьшить масштаб. «Один шаг» оставляет узел и прямых соседей. «Путь от seed» — отдельный режим с направленной цепочкой. Под графом — гипотеза выбранного кластера с внутренними/внешними потоками и получателями. «Перейти к кластеру» выделяет группу и приближает её, сохраняя контекст сети.

Колесо мыши и кнопки +/− меняют масштаб, перетаскивание перемещает граф; реализован pinch двумя пальцами. С клавиатуры на холсте работают +/−, стрелки и Home. Легенда под графом сворачивается и фильтрует шесть ролей; цвет дублируется формой и русским названием. Поиск включает роль выбранного участника, сохраняя остальные настройки; выбор пути включает роли всех его узлов. «Вся сеть» / «Показать всё» восстанавливает все роли, очищает карточку и сохраняет топ. Карточку можно скачать в TXT.

Подпись есть только у выбранного узла и во всплывающих подсказках. Периферия видима по умолчанию, но меньше и бледнее. Толщина ребра ограничена диапазоном 0,6–2,8 px, линейно растёт до 95-го перцентиля суммы; точные суммы всегда доступны в таблице. Тёмное внешнее кольцо отмечает seed, отдельное кольцо — выбранный узел. Янтарные стрелки направлены к выбранному, голубые — от него, золотистая линия отмечает путь. Тёмная палитра, градиентные узлы со свечением и тонкие светящиеся линии помогают отделить активные связи от фона. Контуры обозначают кластеры. Геометрические расстояния не являются метрикой финансовой близости.

[Дизайн, соответствие ТЗ и браузерная проверка](docs/ui-review.md). [Полный код изменённых файлов интерфейса](docs/UI_SOURCE.md).

## Метрики

`sum_in`, `sum_out`, `n_tx_in`, `n_tx_out` считаются по направленным рёбрам. `volume = sum_in + sum_out` — интенсивность участия, не баланс: проходящая сумма может учитываться дважды. `fan_in`, `fan_out` — число уникальных контрагентов без самопереводов; `in_degree`, `out_degree` сохраняют степени исходного графа.

`pass_through_ratio = sum_out / sum_in`, при нулевом входе — NULL. `is_depth4_leaf = depth == 4 and out_degree == 0`. Изоляты сохраняются, даты и ratio могут быть NULL. `activity_span_hours` — окно наблюдаемой активности, не срок удержания средств.

`rapid_out_share` — доля исходящей суммы, которой предшествует хотя бы один вход за 0–24 часа. Используется ближайший предыдущий вход; будущий вход не подходит. Суммы не связываются, один вход может сопровождать несколько выходов. В этой выгрузке даты имеют точность до дня: признак означает тот же или следующий день, порядок внутри дня неизвестен.

`seed_hops`, `seed_path` — минимальная направленная дистанция и один детерминированный путь от любого seed, рассчитанные общим BFS; при недостижимости −1 и пустой путь. При равенстве используются отсортированные gid.

`reachable_seed_count` — сколько различных seed достигают узла за ≤4 шага; `near_seed_count` — за ≤2 шага. Собственный seed не считается. `seed_branch_count` — число непосредственных плательщиков, достижимых от какого-либо seed за ≤3 шага. Это **разные входные ветви, но не гарантированно независимые пути**: они могут иметь общих предков. Циклы не размножают seed. Близость к нескольким seed — контекст структуры, не доказательство координации.

## Формальные правила ролей

Применяется первое подходящее правило. Пороги одинаковы для всех gid; списков «правильных узлов» в расчёте нет. `role_score` — условная сила правила, не откалиброванная вероятность.

| Порядок / роль | Условие | Сила правила |
|---|---|---|
| 1. terminal на границе | depth=4, out_degree=0, вход >0 | 0,25 |
| 2. consolidator | не seed, fan_in ≥5, выход/вход ≤0,2 | 0,80 |
| 3. coordinator | fan_in и fan_out ≥5; большая степень ≤2×меньшей; volume ≥P90; ≥2 seed в пределах двух шагов; ≥2 входные ветви от seed | 0,70 + до 0,10 за дополнительные близкие seed |
| 4. distributor | fan_out ≥5 **и** (fan_out ≥2×max(1, fan_in) **или** известный выход/вход ≥0,8) | 0,65 + 0,15×rapid_out_share |
| 5. transit | не seed; ratio 0,8–1,2; обе степени >0, большая ≤2×меньшей; rapid_out_share ≥0,5 | 0,65 + 0,15×rapid_out_share |
| 6. terminal внутри выборки | вход >0, fan_out=0 | 0,65 |
| 7. peripheral | остальные | 0,40 |

У seed сила любого правила ограничена 0,55, неполнота входа отражена в evidence. Для distributor с нулевым входом также максимум 0,55. Временная доля распределителя **не определяет срабатывание**: значения 49,75% и 50% не меняют структурную роль. При сильной асимметрии распределения роль coordinator не перекрывает distributor. Сбор с малой отдачей проверяется до координации.

Пять контрагентов — эвристическая граница выраженного ветвления. Соотношение 2:1 выделяет асимметрию числа связей, 20% — малый наблюдаемый выход, диапазон 0,8–1,2 — близость сумм. P90 адаптирует условие оборота к выборке. Параметры сохраняются в отчёт. Их точность без размеченных данных не оценивалась; чувствительность к **порогам ролей** и к Louvain resolution пока отдельно не исследована.

## Приоритет и устойчивость

Обозначим `L(x)=log1p(x)/max(log1p(x))`; при нулевом максимуме L=0.

```text
0,15 × вес_роли × role_score
+ 0,25 × L(volume)
+ 0,25 × L(fan_in + fan_out)
+ 0,10 × близость_seed
+ 0,10 × L(reachable_seed_count)
+ 0,15 × L(fan_in) × наблюдаемая_малая_отдача
```

`близость_seed=1/(1+seed_hops)`, для недостижимых — 0. `наблюдаемая_малая_отдача=1−clip(sum_out/sum_in,0,1)`; при неизвестном ratio, у seed и листьев глубины 4 — 0. Последний вклад выделяет сбор от многих плательщиков с малым дальнейшим выходом, чтобы крупное веерное распределение не вытесняло консолидацию из очереди проверки.

Веса ролей: coordinator/consolidator/distributor — 1; transit — 0,8; terminal — 0,35; peripheral — 0,1. Координатор не получает привилегии относительно двух других структурных ролей. Сумма весов 1, балл в 0–1. Все шесть вкладов отображаются в `why` и интерфейсе. При равенстве score сортировка по gid. Абсолютные scores между разными выборками напрямую несопоставимы.

Для каждого из шести весов автоматически проверяются ±20% с последующей нормировкой; отдельно — базовый вариант и вариант без роли: всего **14 сценариев**. `ranking_sensitivity.csv` содержит все места всех узлов, отчёт — пересечение топа и максимальный сдвиг мест. Карточка показывает полный диапазон мест, включая вариант без роли. Это проверка устойчивости **ранжирования**, не оценка accuracy и не доказательство правильности весов.

## Кластеры и их назначение

Взвешенный Louvain (`resolution=1`, `seed=42`) запускается по каждой слабосвязной компоненте. В неориентированной проекции встречные суммы складываются. Изоляты получают отдельные сообщества. Группы нумеруются по минимальному gid; повторный расчёт одинаковых данных детерминирован. Идентификатор кластера может измениться при новых данных.

Для гипотезы рассчитываются внутренние переводы I, вход из других сообществ E_in, выход E_out и доля I/(I+E_in+E_out). Каждое ребро учитывается один раз относительно конкретного кластера; сумма оборотов всех кластеров с внешними потоками будет учитывать межкластерное ребро дважды, поэтому не является общим оборотом сети. `sum_kzt_internal` учитывает только I.

Гипотеза сообщает признаки сбора, распределения и транзита по участникам; назначение может быть смешанным. При отсутствии таких ролей проверяются преобладающий внешний вход/выход (больше противоположного в 1,5 раза и внутренних потоков), сбалансированный внешний обмен (0,8–1,2) или смешанный обмен без определённого назначения. Изолятам назначение не выдумывается. В тексте указаны три крупнейших получателя переводов участников (внутренние и внешние), суммы и число листьев глубины 4. `top_gids` — до пяти участников по приоритету; это отдельный список от получателей.

## Выходные файлы

Три обязательных CSV сохраняют фиксированные схемы:

| Файл | Колонки |
|---|---|
| `nodes_roles.csv` | gid, role, role_score, cluster_id, priority_score, evidence |
| `clusters.csv` | cluster_id, n_nodes, n_seed, sum_kzt_internal, top_gids, hypothesis |
| `top_nodes.csv` | rank, gid, role, priority_score, why |

UTF-8, запятая, заголовок; evidence 1–200 символов. `node_metrics.parquet` содержит метрики и слагаемые, `ranking_sensitivity.csv` — варианты ранжирования, `run_report.json` — размеры, пороги, веса, версии библиотек, SHA-256 входов и время. `graph.html` включает данные, CSS и JS, не загружает CDN или API. Gid при импорте CSV в Excel нужно читать как текст, иначе Excel округлит длинные числа.

## Проверка и архитектура

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Linux/macOS: `.venv/bin/python -m unittest discover -s tests -v`. Пайплайн проверяет входные схемы, NULL, типы, уникальность gid и пар, концы рёбер, суммы, n_tx, порог 5000 KZT и июль 2026; агрегаты сверяются с транзакциями. Проверяются заполненность выходов, границы scores, длина evidence, сохранение узлов и отсутствие объединения разных компонент. Сквозные регрессионные тесты заново считают данные во временную папку.

19 Python-тестов покрывают исчезавших распределителей, требования к координатору, неизвестный вход, обрыв/seed, временное направление, циклы, самопереводы, пути и int64, потоки кластера, изоляты, CSV и воспроизводимость порядка. Ещё 8 тестов камеры, границ толщины, pan и pinch запускаются через `node --test tests/test_graph_ui.cjs` (Node.js нужен только для этих тестов, не для приложения). [Проверка аналитики](docs/verification.md), [проверка нового интерфейса](docs/ui-review.md).

`pipeline/load.py` — валидация; `metrics.py` — граф и признаки; `roles.py` — роли; `clustering.py` — сообщества и потоки; `ranking.py` — приоритет и чувствительность. `run_pipeline.py` связывает этапы; `app/build.py` встраивает `template.html`, `style.css`, `graph.js` (Canvas и камера), `view.js` (элементы интерфейса) и `cases.js` в автономный HTML. `run.py` отвечает за подготовку окружения. `tools/build_defense.py` обновляет примеры защиты из результатов.

## Ограничения и масштабирование

Граф содержит только исходящий обход до 4 колен, внутрибанковские переводы ≥5000 KZT за июль 2026. Входы неполны, граница обрезана, нет остатков, назначения платежа, атрибутов клиентов и ground truth. 354 узла отдают больше наблюдаемого входа: это не подтверждённый «отрицательный баланс». Peripheral означает отсутствие сработавшего правила, а terminal — отсутствие наблюдаемого выхода. Много seed или большое число связей само по себе не доказывает организационную роль.

Все 2248 узлов сохранены: 16 компонент с рёбрами плюс 19 изолятов дают 35 полных компонент. 444 листа глубины 4 явно помечены. Кластеры — структуры переводов, не установленные преступные группы.

При росте до миллиона узлов чтение/агрегацию перенести на DuckDB/Polars и партиционированный Parquet; gid компактно перенумеровать для CSR. NetworkX заменить графовым движком на C/C++, временные признаки считать потоковым as-of проходом. Louvain/Leiden выполнять по компонентам с контролем памяти. Общий BFS имеет O(V+E), но нынешний контекст каждого seed требует до O(S·(V+E)) в худшем случае: при множестве seed нужны ограниченная многометочная передача, битовые множества или явно обозначенная аппроксимация. Сводки кластеров сейчас фильтруют рёбра для каждого кластера — заменить одним групповым проходом.

Сценарии приоритета считать векторно без материализации всех строк при необходимости. Миллион узлов не встраивать в HTML: API поиска, агрегированная карта сообществ, загрузка ограниченных ego-графов и WebGL. Версионировать входы, конфигурацию и результаты, измерять память и задержки на целевом числе рёбер. Требование пяти минут подтверждается только для предоставленной выборки.

## Карточка дела и запросы недостающих данных

Выберите узел и нажмите **«Открыть карточку дела»** либо **«Каких данных не хватает?»**. В карточке показаны evidence с фактическими метриками, транзакции узла, связанные seed и по одному кратчайшему направленному пути от каждого достижимого seed. Цепочки строятся BFS без хардкода gid; временная последовательность пути не проверяется. Путь в месячном графе не доказывает движение одной суммы. Для самого seed отображается путь нулевой длины.

Статусы: «Новое», «Проверяется», «Закрыто», «Эскалировано». Кнопка «Сохранить решение» сохраняет статус и комментарий, добавляя время, предыдущий и новый статус и текст основания в историю. Для закрытия/эскалации комментарий обязателен. При выходе с несохранёнными изменениями появляется предупреждение.

Хранение — `localStorage` текущего браузера, с ключом из SHA-256 входной выборки и gid. После перезагрузки записи сохраняются; другой браузер/адрес, очистка хранилища или изменение входной выборки дают отдельное состояние. Для file:// поддержка хранилища зависит от браузера; предпочтителен локальный HTTP-сервер. При ошибке хранения интерфейс сообщает о ней. Это прототип персональной работы, без авторизации, совместного редактирования и защищённого аудита; дата истории берётся с локальных часов. Очистка браузера удалит историю — экспортируйте нужные дела. JSON-импорт не реализован.

Экспорт:

- **Справка HTML** — автономный документ: факты, роль, комментарий, ограничения, пути, запросы, история и операции; можно распечатать в PDF средствами браузера. Не является регуляторным сообщением ФМ-1.
- **Дело JSON** — структурированная копия метрик, транзакций, контекста, решения и истории с отпечатком данных. Несохранённые изменения явно помечены как черновик.
- **Список запросов TXT** — конкретные запросы с основаниями, gid и отпечатком выборки.

Транзакции имеют ссылку `row:N` на позицию в исходном transactions.parquet (нумерация с 1). Это не банковский идентификатор: одинаковые строки не удаляются и остаются отдельными наблюдениями. Все gid в браузере и экспорте JSON — строки для сохранения точности int64.

Запросы формируются прозрачными условиями в `app/cases.py`:

| Наблюдение | Рекомендованный запрос |
|---|---|
| depth4 leaf | Дальнейшие исходящие переводы, расширение обхода |
| seed, нулевой вход или ratio >1,2 | Полный входящий поток и начальный остаток |
| Есть вход и выход | Точное время, часовой пояс, порядок операций |
| Вход больше выхода | При разрешённом доступе — межбанковские переводы, снятия и другие способы вывода |
| Нет входящих и исходящих связей | Проверка полноты выгрузки и фильтров |
| Для всех | Расширение периода, операции ниже 5000 KZT, полнота каналов |

Приложение лишь формирует запросы для аналитика: внешние данные не запрашиваются и не добавляются. Дополнительные тесты проверяют направление путей, циклы, недостижимые узлы и условия запросов.
````

## docs/ui-review.md

````markdown
# Интерфейс графа: изменения и проверка

Изменён только слой представления: автономный HTML, Canvas 2D и обычный JavaScript. Python-пайплайн, правила ролей, кластеризация, ранжирование и схемы CSV сохранены. Новых библиотек, CDN, API или сборщика JavaScript нет. Откройте `output/graph.html` либо запустите проект обычной командой из README.

## Соответствие исходному ТЗ

Сопоставление выполнено с документом «ТЗ кейса для HackAlem AI.docx» в корне репозитория, прежде всего с разделами 3, 5, 7 и 9.

| Требование | Реализация |
|---|---|
| Найти произвольный gid и показать его связи | Всегда доступный поиск с подсказками по фрагменту, выбор с клавиатуры, автоматическое центрирование и приближение, подсветка прямых связей |
| Видеть направление денег | Стрелки на рёбрах; при выборе входящие и исходящие различаются цветом, направления подписаны в таблице |
| Видеть роли и кластеры | Шесть цветов и шесть форм, русские названия с исходным кодом роли в карточке; контуры кластеров, выбор из списка и описание назначения |
| Топ не менее 20 узлов с объяснениями | Постоянный топ-30 с rank, gid, ролью, priority_score и раскрываемым why; выбор не заменяет список |
| Объяснить роль произвольного узла | Справа role_score, evidence, кластер, суммы, число контрагентов, все прямые связи, слагаемые приоритета и доступные пути |
| Сохранить все узлы, учитывать ограничения | По умолчанию 2248 узлов, включая периферию и изоляты; сохранены сообщения о seed, неизвестном входе и границе 4-го колена |
| Локальный запуск | Один HTML со встроенными данными, CSS и JavaScript; интернет, Node.js и сервер для просмотра не нужны |
| Осторожность выводов | Балл описан как сила правила, а не вероятность нарушения; контур кластера не объявляет группу преступной; путь не доказывает движение одной суммы |

Переработка UI поддерживает обязательный сценарий ТЗ. Она не проверяет точность ролей и сама по себе не доказывает выполнение всех требований к аналитическому решению. Проверки расчётов описаны отдельно в `verification.md`.

## Принятые решения по дизайну

1. Полная сеть остаётся доступна по умолчанию. У периферии меньше размер и прозрачность, но она не исключена: даже такой узел может соединять важные участки сети.
2. Легенда находится в выделенной полосе под холстом и изначально свёрнута. Она не закрывает узлы. При низком экране кнопки навигации переходят в отдельную горизонтальную полосу.
3. Выбор узла приближает его и локальное окружение. «Фокус» вмещает все видимые прямые связи. Дальние контрагенты могут потребовать уменьшения масштаба; одно действие не может одновременно показать всю растянутую сеть и крупный узел. Все суммы остаются в карточке, «Один шаг» убирает посторонние узлы.
4. Кластеры показаны нейтральными контурами: отдельная яркая палитра на 105 кластеров конфликтовала бы с цветами шести ролей. Группы определяются существующим backend; экранное расположение условное.
5. Постоянных подписей 2248 узлов нет. Gid и роль видны у выбранного узла и в подсказке при наведении. Подсказка фона показывает номер и полный размер кластера; счётчик графа учитывает фильтры.
6. Толщина пропорциональна сумме до 95-го перцентиля, затем ограничена. Диапазон 0,6–2,8 CSS px относится к сердцевине линии и не зависит от зума; мягкое свечение рисуется снаружи. Ограничение явно подписано, точные значения не округляются в данных и доступны в карточке. В этой выборке верхний порог — 450 000 KZT.
7. На широком экране одновременно доступны список, граф и карточка. На узком — вкладки в той же странице, сохраняющие выбор; три узкие колонки были бы нечитаемыми. Поиск остаётся наверху во всех вкладках.
8. Роль передаётся цветом, формой и текстом. Для Canvas есть управление клавиатурой; поиск, топ и таблицы дают альтернативный способ выбора без попадания мышью в мелкий узел. Полный аудит WCAG и тестирование со скринридером не проводились.

## Управление

- Колесо масштабирует относительно курсора; +/− — относительно центра холста.
- Перетаскивание перемещает граф. После drag или pinch отпускание не выбирает случайный узел.
- Два указателя touch масштабируют вокруг их движущегося центра. `touch-action: none` применяется только к холсту; панели продолжают прокручиваться.
- «Фокус» вмещает выбранный узел с видимыми прямыми связями либо выбранный кластер. «Показать всё» / «Вся сеть» очищает выбор и фильтры, возвращает общий вид.
- На сфокусированном холсте: +/−, стрелки и Home. В поиске: минимум 3 символа для подсказок, стрелки, Enter, Escape.
- В таблице переводов можно выбрать входящие, исходящие или все связи и изменить порядок сумм. Самопереводы отмечены отдельно; строки не обрезаются по количеству.
- «Один шаг» и «Путь от seed» взаимоисключающие. Путь показан отдельной вертикальной цепочкой; его направление и идентификаторы берутся из готовых результатов.

## Файлы

```text
app/
  build.py          Встраивание нового graph.js в автономный HTML
  template.html     Семантическая разметка, поиск, панели, Canvas, кнопки
  style.css         Тёмная тема, адаптивность, доступный фокус
  graph.js          Камера, жесты, рёбра, формы, контуры, hit testing
  view.js           Поиск, фильтры, топ, карточка, таблицы, переключение областей
  cases.py          Существующая логика дела, без изменений
  cases.js          Существующий интерфейс дела и сохранение, без изменений
tests/
  test_graph_ui.cjs Тесты геометрии и жестов без сторонних пакетов
docs/
  ui-review.md      Этот документ
  UI_SOURCE.md     Полный код изменённых исходных файлов
README.md          Обновлённый сценарий и команды проверки
output/
  graph.html        Полностью автономный результат с данными
```

## Результаты проверки, 23 сентября 2026

Автоматически:

- 19 Python-тестов прошли, включая полный пересчёт во временную папку, контракты CSV, роли, пути, дела и автономную сборку HTML.
- 8 JavaScript-тестов прошли: сохранение точки под курсором, ограничения зума, охват далёких соседей, изолят, автофокус, монотонность и пределы толщины, pan, pinch, отмена указателя и последующий tap. Некоторые тесты проверяют несколько связанных условий.
- SHA-256 всех шести файлов `pipeline/*.py`, трёх входных Parquet и трёх обязательных CSV совпадают с состоянием до изменения UI.
- Встроенные `nodes`, `edges`, `clusters`, `transactions`, `cases`, `top`, `stability` и `fingerprint` полностью совпадают с прежним HTML. Сохранён ключ localStorage для существующих дел.

В живом браузере:

- Поиск распределителя `100000002578405100` по фрагменту и выбор стрелкой/Enter. Роль и точный gid сохранены; таблица содержит 118 направленных связей: 2 входящие и 116 исходящих, 117 уникальных участников в режиме одного шага.
- Сортировка всех сумм в обе стороны, фильтры направлений, переход к кластеру 33 (112 участников), путь от seed из трёх узлов и двух рёбер.
- Зум кнопками и колесом, drag без выбора узла, фокус и сброс; топ-30 остаётся на месте после выбора, фильтрации и сброса.
- Фильтр периферии: 1706 видимых узлов; отключение всех ролей и восстановление; возврат скрытого выбранного узла через «Фокус»; сообщение об отсутствии неизвестного gid.
- Карточка изолированного seed, предупреждение границы четвёртого колена, открытие и закрытие прежней карточки дела.
- Разрешения 390×640, 390×844, 1024×600, 1920×1080 и обычное окно браузера: без внешнего горизонтального/вертикального переполнения. Проверены вкладки телефона, сохранение выбора, поиск и доступность кнопок.
- В 12 последовательных изменениях масштаба на экране 1920×1080 измеренное время JavaScript-отрисовки Canvas составило 1,1–5,4 мс. Это локальная выборка, не полная стоимость кадра с композицией и не гарантия FPS на другом устройстве.
- В консоли браузера ошибок и предупреждений не было.

Pinch проверен тестом геометрии двух указателей; физический телефон или сенсорный монитор в этой проверке не использовался. Hover-подсказки реализованы, но отдельный автоматизированный прогон наведения не выполнялся. Существующий экспорт дел не менялся; загрузки файлов и сохранение новых решений в этом UI-прогоне не проверялись.

## Производительность и границы

Canvas отрисовывается по требованию через `requestAnimationFrame`; несколько событий объединяются в один кадр. Смежность и параметры рёбер подготовлены один раз, фильтрация перестраивается при изменении выбора/режима. Узлы и рёбра за пределами холста пропускаются при рисовании. DPR ограничен 2; нет force simulation, непрерывной анимации или отдельных DOM-элементов для каждого узла графа.

На общем плане близко расположенные узлы неизбежно перекрываются. Используйте поиск, кластер или приближение для чтения конкретных связей. Произвольные миллионы узлов этим Canvas-компонентом не проверялись; соответствующий план масштабирования в README сохранён.

## Обновление оформления: тёмная тема

По запросу пользователя изменены только палитра CSS и рисование Canvas в `app/graph.js`. Сохранены размеры панелей, управление, поиск, таблицы, формы ролей, все данные и ключи дел. Фон — тёмно-синий, основной текст — светлый, вторичный — серо-голубой; уведомления, формы, таблицы и модальное окно согласованы с темой.

Узлы получили градиентный объём, блик и мягкий цветной ореол. Для шести ролей один раз создаются текстуры 112×112; при рисовании каждого узла нет отдельного blur. Активные рёбра используют прозрачную внешнюю линию и тонкую светлую сердцевину; направление по-прежнему отмечено стрелкой. Непрерывной анимации нет.

Проверены поиск с подсказкой, выбор узла, карточка дела, общий вид и кнопки зума. В восьми изменениях масштаба отрисовка заняла 2,0–7,1 мс в текущем окне браузера; сравнивать напрямую с прежним замером на другом размере окна нельзя. Восемь тестов камеры и жестов прошли. SHA-256 файлов поведения, пайплайна, выходных данных и встроенного JSON совпадают с состоянием перед сменой темы.
````

