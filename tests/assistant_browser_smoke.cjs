// Live browser acceptance: requires the real local model, never mocks /ask.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch({headless:true,channel:process.env.BROWSER_CHANNEL||'chrome'});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(process.env.AML_URL||'http://127.0.0.1:8765/graph.html');
    await page.locator('#insights').click();
    await page.locator('#insightTabs button').filter({hasText:'Помощник'}).click();
    await page.waitForFunction(()=>document.querySelector('#assistantMode').value==='llm');
    assert.match(await page.locator('#assistantStatus').innerText(),/Qwen.*CPU.*готов/);
    const question='Найди одного приоритетного консолидатора и покажи направленный путь от seed к нему.';
    await page.locator('#assistantQuestion').fill(question);
    await page.locator('#assistantForm button').click();
    await page.waitForFunction(()=>typeof assistantLast!=='undefined'&&assistantLast?.question===
      'Найди одного приоритетного консолидатора и покажи направленный путь от seed к нему.',{},{timeout:170000});
    const result=await page.evaluate(()=>assistantLast);
    assert.equal(result.status,'answered');
    assert.equal(result.mode,'llm_agent');
    assert.ok(result.trace.some(s=>s.action==='top_nodes'&&s.status==='ok'));
    assert.ok(result.trace.some(s=>s.action==='seed_paths'&&s.status==='ok'));
    assert.ok(await page.locator('#assistantAnswer .assistant-fact').count()>=2);
    await page.locator('#assistantTrace summary').click();
    assert.match(await page.locator('#assistantTrace').innerText(),/finish/);
    const pending=page.waitForEvent('download');
    await page.locator('#exportAssistant').click();
    const download=await pending,parts=[];
    for await(const chunk of await download.createReadStream())parts.push(chunk);
    assert.deepEqual(JSON.parse(Buffer.concat(parts).toString()),result);
    if(process.env.AML_SCREENSHOT)await page.screenshot({path:process.env.AML_SCREENSHOT});
    await page.locator('#assistantAnswer button').filter({hasText:'Показать путь на графе'}).first().click();
    assert.ok(await page.evaluate(()=>activePath.length>1&&visible.length===activePath.length));
    assert.deepEqual(errors,[]);
    fs.writeFileSync('output/assistant_browser_report.json',JSON.stringify({status:'passed',live_llm:true,
      model:result.model,engine:result.engine,analysis_sha256:result.analysis_sha256,
      checks:['Real CPU model available','Multi-step tool calls','Evidence and trace rendered','JSON export matches answer','Path opens on graph','No browser errors'],
      result},null,2));
    console.log('Live LLM browser smoke passed: tools, evidence, trace, JSON export and graph path.');
  } finally {await browser.close()}
})().catch(error=>{console.error(error);process.exit(1)});
