// Real LLM agent and explicitly labelled deterministic quick-search mode.
let assistantBusy=false,assistantLast=null;
function renderAssistant(root){
  addText(root,'h3','Помощник аналитика');
  addText(root,'p','LLM-агент выбирает инструменты, проверяет граф и собирает ответ со ссылками на факты. Режим «Быстрый поиск» выполняет заранее заданные запросы без модели.');
  const status=addText(root,'p','Проверяю доступность локальной модели…','notice');status.id='assistantStatus';
  const form=addText(root,'form','');form.id='assistantForm';
  const modeLabel=addText(form,'label','Режим '),mode=addText(modeLabel,'select','');mode.id='assistantMode';
  for(const [value,label] of [['rules','Быстрый поиск — без LLM'],['llm','LLM-агент — локально, CPU']]){const option=addText(mode,'option',label);option.value=value}
  let explicitlySelected=false;mode.onchange=()=>{explicitlySelected=true};
  const input=addText(form,'textarea','');input.id='assistantQuestion';input.maxLength=2000;input.rows=3;
  input.placeholder='Найди приоритетного консолидатора и объясни, каких данных для его проверки не хватает.';
  input.setAttribute('aria-label','Вопрос помощнику');
  const submit=addText(form,'button','Спросить');submit.type='submit';
  const answer=addText(root,'div','');answer.id='assistantAnswer';answer.setAttribute('aria-live','polite');
  const samples=addText(root,'div','','case-actions');
  for(const q of ['Кого смотреть первым?','Найди одного приоритетного консолидатора и покажи путь от seed к нему.',
                  `Объясни роль ${selected||data.demo[0]?.gid||data.nodes[0].gid} и предложи, каких данных не хватает.`]){
    const button=addText(samples,'button',q);button.type='button';button.onclick=()=>{input.value=q;input.focus()};
  }
  addText(root,'p','Можно сравнить несколько gid, найти общих получателей, посмотреть циклы и запросить недостающие данные. Максимум шесть шагов, до 150 секунд на CPU.','muted');
  if(assistantLast)renderAgentAnswer(answer,assistantLast);
  if(location.protocol==='file:'){
    status.textContent='Готовый HTML поддерживает быстрый поиск. Для LLM запустите проект через run.sh --serve или run.bat --serve и откройте адрес сервера.';
  }else{
    fetch('/api/assistant/status',{cache:'no-store',signal:AbortSignal.timeout(4000)})
      .then(r=>{if(!r.ok)throw Error();return r.json()})
      .then(info=>{status.textContent=info.available?`${info.model} · CPU · локально · готов к работе`:
        (info.reason||'Локальный LLM не запущен. Установите модель и перезапустите сервер.');
        if(info.available&&!explicitlySelected)mode.value='llm';})
      .catch(()=>{status.textContent='Этот сервер не поддерживает LLM API. Запустите актуальный run.sh --serve или run.bat --serve. Быстрый поиск доступен.'});
  }
  form.onsubmit=async event=>{
    event.preventDefault();if(assistantBusy)return;
    const question=input.value.trim();if(!question){input.focus();return}
    if(mode.value==='rules'){answerQuestion(question,answer);return}
    if(location.protocol==='file:'){answer.replaceChildren();addText(answer,'p','LLM требует запущенного локального сервера. Откройте адрес из терминала после запуска с --serve.');return}
    assistantBusy=true;submit.disabled=true;mode.disabled=true;answer.replaceChildren();
    const waiting=addText(answer,'p','LLM выбирает инструменты и проверяет граф…','notice');
    const start=Date.now(),timer=setInterval(()=>{waiting.textContent=`Проверяю граф локально на CPU… ${Math.floor((Date.now()-start)/1000)} с`},1000);
    try{
      const response=await fetch('/api/assistant/ask',{method:'POST',headers:{'Content-Type':'application/json','X-AML-Request':'1'},
        body:JSON.stringify({question,selected_gid:selected,dataset_sha256:data.fingerprint,analysis_sha256:data.analysis_sha256}),signal:AbortSignal.timeout(170000)});
      const result=await response.json();
      if(!response.ok)throw Error(result.error||'Помощник недоступен.');
      assistantLast=result;renderAgentAnswer(answer,result);
    }catch(error){answer.replaceChildren();addText(answer,'p',error.name==='TimeoutError'?'Истекло время ожидания. Сервер может ещё завершать запрос; повторите позже.':error.message,'notice');
      addText(answer,'p','Ответ LLM не получен. Можно явно выбрать «Быстрый поиск»; он не использует модель.','muted');
    }finally{clearInterval(timer);assistantBusy=false;submit.disabled=false;mode.disabled=false}
  };
}
function renderAgentAnswer(root,result){
  root.replaceChildren();
  addText(root,'h3',result.status==='answered'?'Ответ по графу':result.status==='partial'?'Частичный результат':'Нужно уточнение или настройка');
  addText(root,'p',result.message,result.status==='answered'?'muted':'notice');
  addText(root,'p',`${result.model||'Локальная модель'} · ${result.model_calls} вызовов LLM · ${result.elapsed_seconds} с · CPU`,'muted');
  for(const fact of result.findings||[]){
    const card=addText(root,'section','','assistant-fact');addText(card,'strong',`[${fact.ref}]`);addText(card,'p',fact.text);
    for(const gid of fact.gids)nodeLink(card,gid,'Открыть '+gid);
    if(fact.values?.path){const button=addText(card,'button','Показать путь на графе');button.onclick=()=>showPath(fact.values.path)}
    const raw=addText(card,'details','');addText(raw,'summary','Исходные значения');addText(raw,'pre',JSON.stringify(fact.values,null,2));
  }
  const trace=addText(root,'details','');trace.id='assistantTrace';
  addText(trace,'summary',`Действия агента и источники (${result.trace.length})`);
  for(const step of result.trace){addText(trace,'p',`${step.step}. ${step.action} · ${step.status} · ${(step.refs||[]).join(', ')}`);if(step.arguments)addText(trace,'pre',JSON.stringify(step.arguments,null,2));if(step.error)addText(trace,'p',step.error)}
  for(const limitation of result.limitations||[])addText(root,'p',limitation,'muted');
  const button=addText(root,'button','Скачать ответ и журнал JSON');button.id='exportAssistant';
  button.onclick=()=>downloadCase('assistant-investigation.json',JSON.stringify(result,null,2),'application/json');
}
