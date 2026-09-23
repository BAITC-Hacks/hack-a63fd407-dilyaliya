/* Application UI. Global helpers remain compatible with the existing cases.js. */
'use strict';
<<<<<<< HEAD
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
=======
const colors={coordinator:'#c084fc',consolidator:'#fb7185',distributor:'#fbbf24',transit:'#38bdf8',terminal:'#4ade80',peripheral:'#8190a8'};
const labels={coordinator:'Координация',consolidator:'Консолидация',distributor:'Распределение',transit:'Транзит',terminal:'Получатель',peripheral:'Периферия'};
const $=id=>document.getElementById(id), canvas=$('canvas'), ctx=canvas.getContext('2d');
const map=new Map(data.nodes.map(n=>[n.gid,n])), clusters=new Map(data.clusters.map(c=>[c.cluster_id,c]));
const fmt=value=>Number(value).toLocaleString('ru-RU',{maximumFractionDigits:0});
const adjacency=new Map(data.nodes.map(n=>[n.gid,[]]));
for(const e of data.edges){adjacency.get(e.src).push(e);if(e.src!==e.dst)adjacency.get(e.dst).push(e)}
const topMap=new Map(data.top.map(n=>[n.gid,n]));
let width=1,height=1,scale=1,ox=0,oy=0,selected=null,visible=[],links=[],pathIds=new Set(),pathEdges=new Set(),activePath=[];
function addText(parent,tag,text,className){const e=document.createElement(tag);e.textContent=text;if(className)e.className=className;parent.append(e);return e}
for(const [value,title] of [[data.nodes.length,'узлов'],[data.edges.length,'связей'],[data.clusters.length,'кластеров']]){const box=addText($('overview'),'div','');addText(box,'strong',fmt(value));addText(box,'span',title)}
for(const [role,color] of Object.entries(colors)){const el=addText($('legend'),'span','');const dot=addText(el,'i','','dot');dot.style.background=color;el.append(document.createTextNode(labels[role]));const option=addText($('role-filter'),'option',labels[role]);option.value=role}
for(const cluster of data.clusters){const o=addText($('cluster'),'option',`Кластер ${cluster.cluster_id} · ${cluster.n_nodes} узл.`);o.value=cluster.cluster_id}
$('top-title').textContent=`Приоритетные узлы · ${data.top.length}`;
const perturbations=data.stability.filter(s=>s.scenario!=='baseline'&&s.scenario!=='without_role');
if(perturbations.length){const retained=Math.min(...perturbations.map(s=>s.top_overlap));addText($('stability'),'p',`При изменении весов ±20% в топе остаются минимум ${retained} из ${data.top.length} узлов. Это устойчивость списка, не точность ролей.`,'muted')}
for(const row of data.top){const b=addText($('top'),'button','','candidate');b.dataset.gid=row.gid;b.setAttribute('aria-pressed','false');addText(b,'strong',`${row.rank}. ${row.gid}`);addText(b,'span',row.priority_score.toFixed(3),'candidate-score');addText(b,'span',labels[row.role]);b.onclick=()=>choose(row.gid)}
function refreshSelection(){for(const b of $('top').children)b.setAttribute('aria-pressed',String(b.dataset.gid===selected))}
function updatePath(){const path=map.get(selected)?.seed_path||[];pathIds=new Set(path);pathEdges=new Set(path.slice(1).map((gid,i)=>`${path[i]}>${gid}`))}
function filter(){const adjacent=new Set([selected]);for(const e of adjacency.get(selected)||[]){adjacent.add(e.src);adjacent.add(e.dst)}visible=data.nodes.filter(n=>(!activePath.length||activePath.includes(n.gid))&&($('cluster').value===''||n.cluster_id===Number($('cluster').value))&&($('role-filter').value===''||n.role===$('role-filter').value)&&(!$('route-only').checked||!selected||pathIds.has(n.gid))&&(!$('neighbors').checked||!selected||adjacent.has(n.gid)||pathIds.has(n.gid)));const ids=new Set(visible.map(n=>n.gid));links=data.edges.filter(e=>ids.has(e.src)&&ids.has(e.dst)&&(!$('route-only').checked||!selected||pathEdges.has(`${e.src}>${e.dst}`)))}
function point(n){if(document.getElementById("route-only").checked && selected && pathIds.has(n.gid)){return {x:0,y:(map.get(selected).seed_path.indexOf(n.gid))*120}}return n}
function fit(){filter();if(!visible.length){draw();return}const xs=visible.map(n=>point(n).x),ys=visible.map(n=>point(n).y),xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);scale=Math.min(width/(xmax-xmin+90),height/(ymax-ymin+90),4);ox=width/2-(xmin+xmax)/2*scale;oy=height/2-(ymin+ymax)/2*scale;draw()}
const radius=n=>Math.max(2.7,(3+6*n.priority_score)*Math.sqrt(scale));
function draw(){ctx.clearRect(0,0,width,height);const sorted=[...links].sort((a,b)=>Number(pathEdges.has(`${a.src}>${a.dst}`))-Number(pathEdges.has(`${b.src}>${b.dst}`)));for(const e of sorted){const a=map.get(e.src),b=map.get(e.dst),path=pathEdges.has(`${e.src}>${e.dst}`),active=e.src===selected||e.dst===selected;let x=point(a).x*scale+ox,y=point(a).y*scale+oy,xx=point(b).x*scale+ox,yy=point(b).y*scale+oy,angle=Math.atan2(yy-y,xx-x);ctx.strokeStyle=path?'#ffcb6b':active?'#dce7f5':selected?'#33415550':'#61718b60';ctx.fillStyle=ctx.strokeStyle;ctx.lineWidth=path?3:active?1.5:.6;if(a===b){ctx.beginPath();ctx.arc(x+8,y-8,10,0,Math.PI*1.8);ctx.stroke();continue}xx-=Math.cos(angle)*(radius(b)+1);yy-=Math.sin(angle)*(radius(b)+1);ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(xx,yy);ctx.stroke();const s=path?9:active?7:4;ctx.beginPath();ctx.moveTo(xx,yy);ctx.lineTo(xx-s*Math.cos(angle-.5),yy-s*Math.sin(angle-.5));ctx.lineTo(xx-s*Math.cos(angle+.5),yy-s*Math.sin(angle+.5));ctx.fill()}
for(const n of visible){const x=point(n).x*scale+ox,y=point(n).y*scale+oy;ctx.beginPath();ctx.arc(x,y,radius(n),0,Math.PI*2);ctx.fillStyle=colors[n.role];ctx.fill();if(n.is_seed||n.gid===selected||pathIds.has(n.gid)){ctx.strokeStyle=n.gid===selected?'#ffffff':pathIds.has(n.gid)?'#ffcb6b':'#d5e1f2';ctx.lineWidth=n.gid===selected?3:1.5;ctx.stroke()}if(n.gid===selected||($('route-only').checked&&pathIds.has(n.gid))||scale>2){ctx.fillStyle='#fff';ctx.font='11px system-ui';ctx.fillText(n.gid,x+9,y-7)}}$('stats').textContent=`${visible.length} узлов · ${links.length} направленных рёбер${visible.length?'':' · ослабьте фильтры'}`}
function renderCluster(){const cid=$('cluster').value!==''?Number($('cluster').value):map.get(selected)?.cluster_id;const c=clusters.get(cid),box=$('cluster-summary');box.replaceChildren();if(!c){addText(box,'strong','От сети к проверяемой гипотезе');addText(box,'p','Выберите кандидата слева или найдите gid. Здесь появятся потоки и назначение его кластера.','muted');return}addText(box,'strong',`Кластер ${c.cluster_id} · ${c.n_nodes} узлов · ${c.n_seed} seed`);addText(box,'p',c.hypothesis)}
function emptyDetail(){const d=$('node-detail');d.replaceChildren();addText(d,'h3','Начните с приоритетного узла');addText(d,'p','Карточка объяснит роль, покажет входящие и исходящие переводы и кратчайший направленный путь от seed.','empty');addText(d,'p','Размещение группирует сообщества. Расстояния на экране не являются мерой финансовой близости.','muted')}
function choose(gid){const n=map.get(gid);if(!n){$('gid').setCustomValidity('Такой gid отсутствует в выборке');$('gid').reportValidity();return}$('gid').setCustomValidity('');selected=gid;activePath=[];document.getElementById("card-preview").hidden=true;$('gid').value=gid;$('cluster').value='';$('role-filter').value='';$('export-card').disabled=false;updatePath();refreshSelection();renderCluster();const d=$('node-detail');d.replaceChildren();d.parentElement.scrollTop=0;addText(d,'h3',gid,'gid-title');addText(d,'p',`${labels[n.role]} · ${n.role} · сила правила ${n.role_score.toFixed(2)}`,'role-label');addText(d,'p',n.evidence);if(n.is_depth4_leaf||n.is_seed||n.zero_sum_in){addText(d,'p',n.is_depth4_leaf?'Граница выборки: дальнейшие переводы не наблюдаются. Это не доказательство оседания денег.':n.is_seed?'Вход seed неполон; отношение выхода ко входу ненадёжно.':'Вход не наблюдается; источник средств по выборке неизвестен.','notice')}
const metrics=addText(d,'div','','metrics');for(const [value,title] of [[`${fmt(n.sum_in)} KZT`,'Наблюдаемый вход'],[`${fmt(n.sum_out)} KZT`,'Наблюдаемый выход'],[fmt(n.fan_in),'Плательщиков'],[fmt(n.fan_out),'Получателей']]){const box=addText(metrics,'div','','metric');addText(box,'strong',value);addText(box,'span',title)}
addText(d,'h3',`Приоритет ${n.priority_score.toFixed(4)}`);for(const [key,title] of [['role','Роль'],['volume','Оборот'],['fan','Связи'],['seed','Близость seed'],['context','Охват seed'],['collection','Сбор с малой отдачей']]){const line=addText(d,'div','','contribution');addText(line,'span',title);addText(line,'strong',n[`priority_${key}`].toFixed(4))}addText(d,'p',`Место при разных весах: ${n.rank_min}–${n.rank_max}. Seed в пределах 2 / 4 шагов: ${n.near_seed_count} / ${n.reachable_seed_count}. Входных ветвей от seed: ${n.seed_branch_count}.`,'muted');if(topMap.has(gid))addText(d,'p',topMap.get(gid).why,'muted');
const index=data.top.findIndex(row=>row.gid===gid),nav=addText(d,'div','','nav-buttons');for(const [label,next] of [['← Предыдущий',index-1],['Следующий →',index+1]]){const b=addText(nav,'button',label);b.disabled=index<0||next<0||next>=data.top.length;b.onclick=()=>choose(data.top[next].gid)}
addText(d,'h3','Путь от seed');const path=n.seed_path||[];if(!path.length)addText(d,'p','Направленный путь от seed в выборке отсутствует.','muted');else{for(let i=0;i<path.length;i++){if(i){const edge=(adjacency.get(path[i-1])||[]).find(e=>e.src===path[i-1]&&e.dst===path[i]);addText(d,'span',`↓ ${fmt(edge.sum_kzt)} KZT · ${edge.n_tx} переводов`,'path-arrow')}const b=addText(d,'button',path[i]+(i===0?' · seed':''),'path-node');b.onclick=()=>choose(path[i])}const b=addText(d,'button','Показать только этот путь');b.onclick=()=>{$('route-only').checked=true;$('neighbors').checked=false;$('cluster').value='';$('role-filter').value='';fit()}}addText(d,'p','Кратчайший путь по направлению рёбер. Суммы — агрегаты за месяц; непрерывная цепочка тех же денег и порядок во времени не установлены.','muted');
const caseButton=addText(d,'button','Открыть карточку дела');caseButton.id='openCase';caseButton.onclick=()=>openCase(gid);const requestButton=addText(d,'button','Каких данных не хватает?');requestButton.id='openRequests';requestButton.onclick=()=>{openCase(gid);document.getElementById('requestsSection').scrollIntoView()};addText(d,'h3','Правило и устойчивость');addText(d,'p',n.rule_text);addText(d,'p',`Сохранение роли при изменении порогов: ${(100*n.role_stability).toFixed(0)}%; ранг ${n.threshold_rank_min}–${n.threshold_rank_max}. ${n.anomaly_evidence}`,'muted');addText(d,'p',`FIFO: 1–2 дня ${(100*n.fifo_strict_share).toFixed(1)}%; 0–2 дня ${(100*n.fifo_same_day_possible_share).toFixed(1)}%. Сценарии сохраняют суммы и не доказывают происхождение денег.`);addText(d,'h3','Время и полнота данных');addText(d,'p',`Окно активности: ${n.activity_span_hours??'нет'} ч. Исходящая сумма рядом с входом ≤24ч: ${(100*n.rapid_out_share).toFixed(1)}%.`);addText(d,'p','Даты точны до дня. Временное соседство лишь поддерживает гипотезу. Для проверки нужны полные выписки, точное время, начальные остатки и назначения платежей.','muted');
const related=[...(adjacency.get(gid)||[])].sort((a,b)=>b.sum_kzt-a.sum_kzt||a.src.localeCompare(b.src)||a.dst.localeCompare(b.dst));addText(d,'h3',`Переводы · ${related.length} связей`);if(!related.length)addText(d,'p','Узел изолирован: в выгрузке нет переводов.','muted');for(const e of related){const other=e.src===gid?e.dst:e.src;const b=addText(d,'button',`${e.src} → ${e.dst}\n${fmt(e.sum_kzt)} KZT · ${e.n_tx} переводов`,'link');b.onclick=()=>choose(other)}filter();if($('neighbors').checked||$('route-only').checked)fit();else{scale=Math.max(scale,1.2);ox=width/2-point(n).x*scale;oy=height/2-point(n).y*scale;draw()}}
$('search').onsubmit=e=>{e.preventDefault();choose($('gid').value.trim())};$('gid').oninput=()=>$('gid').setCustomValidity('');
$('reset').onclick=()=>{selected=null;activePath=[];document.getElementById("card-preview").hidden=true;pathIds.clear();pathEdges.clear();$('gid').value='';$('gid').setCustomValidity('');$('neighbors').checked=false;$('route-only').checked=false;$('cluster').value='';$('role-filter').value='';$('export-card').disabled=true;refreshSelection();emptyDetail();renderCluster();fit()};
$('cluster').onchange=()=>{activePath=[];updatePath();$('route-only').checked=false;$('neighbors').checked=false;renderCluster();fit()};$('role-filter').onchange=()=>{activePath=[];updatePath();$('route-only').checked=false;fit()};$('neighbors').onchange=()=>{activePath=[];updatePath();if($('neighbors').checked){$('route-only').checked=false;$('cluster').value='';$('role-filter').value='';renderCluster()}fit()};$('route-only').onchange=()=>{activePath=[];updatePath();if($('route-only').checked){$('neighbors').checked=false;$('cluster').value='';$('role-filter').value='';renderCluster()}fit()};
$('export-card').onclick=()=>{if(!selected)return;const content=$('node-detail').innerText+'\n\n'+$('cluster-summary').innerText;const url='data:text/plain;charset=utf-8,'+encodeURIComponent(content),a=document.createElement('a');a.href=url;a.download=`node-${selected}.txt`;document.getElementById("card-text").value=content;document.getElementById("card-preview").hidden=false;document.getElementById("card-preview").open=true;document.body.append(a);a.click();a.remove()};
let drag=null;canvas.onpointerdown=e=>{drag={x:e.offsetX,y:e.offsetY,ox,oy,moved:false};canvas.setPointerCapture(e.pointerId)};canvas.onpointermove=e=>{if(!drag)return;const dx=e.offsetX-drag.x,dy=e.offsetY-drag.y;drag.moved ||=Math.hypot(dx,dy)>4;ox=drag.ox+dx;oy=drag.oy+dy;draw()};canvas.onpointerup=e=>{if(drag&&!drag.moved){const candidates=visible.map(n=>({n,d:Math.hypot(point(n).x*scale+ox-e.offsetX,point(n).y*scale+oy-e.offsetY)})).filter(v=>v.d<radius(v.n)+5).sort((a,b)=>a.d-b.d);if(candidates.length)choose(candidates[0].n.gid)}drag=null};canvas.onpointercancel=()=>{drag=null};canvas.onwheel=e=>{e.preventDefault();const next=Math.max(.03,Math.min(15,scale*Math.exp(-e.deltaY*.001)));ox=e.offsetX-(e.offsetX-ox)*next/scale;oy=e.offsetY-(e.offsetY-oy)*next/scale;scale=next;draw()};
emptyDetail();renderCluster();new ResizeObserver(()=>{const r=canvas.getBoundingClientRect();width=r.width;height=r.height;canvas.width=width*devicePixelRatio;canvas.height=height*devicePixelRatio;ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);if(selected && !document.getElementById("route-only").checked && !document.getElementById("neighbors").checked && document.getElementById("cluster").value==="" && document.getElementById("role-filter").value===""){filter();const n=map.get(selected);scale=Math.max(scale,1.2);ox=width/2-n.x*scale;oy=height/2-n.y*scale;draw()}else fit()}).observe($('stage'));
>>>>>>> origin/main

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
