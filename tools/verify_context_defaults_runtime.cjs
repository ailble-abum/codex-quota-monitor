// Chromium CDP -> real monitor -> bundled Codex RPC, with an isolated CODEX_HOME.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const readline = require('node:readline');
const {chromium} = require('playwright');
(async () => {
  const [consumer, cli] = process.argv.slice(2);
  assert.ok(consumer && cli, 'Usage: verify_context_defaults_runtime.cjs CONSUMER CODEX_CLI');
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'quota-context-runtime-'));
  let context, worker;
  try {
    await fs.mkdir(path.join(root, 'home'));
    await fs.mkdir(path.join(root, 'logs'));
    const config = path.join(root, 'home/config.toml');
    await fs.writeFile(config, '# keep\nmodel = "gpt-6.1-sol"\nweb_search = "disabled"\n');
    await fs.writeFile(path.join(root, 'logs/rollout-date-one.jsonl'), JSON.stringify({type:'session_meta',payload:{id:'one'}})+'\n');
    await fs.copyFile(consumer, path.join(root, 'consumer.js'));
    context = await chromium.launchPersistentContext(path.join(root, 'browser'), {headless: true, args:['--remote-debugging-port=0']});
    const page = context.pages()[0];
    await page.route('**/*', route => route.fulfill({body:'<html><head></head><body><div data-app-action-sidebar-thread-row data-app-action-sidebar-thread-active="true" data-app-action-sidebar-thread-kind="local" data-app-action-sidebar-thread-host-id="local" data-app-action-sidebar-thread-id="one"></div></body></html>'}));
    await page.goto('http://context-runtime.invalid/');
    await page.evaluate(() => localStorage.setItem('cti-language','zh'));
    const port = Number((await fs.readFile(path.join(root,'browser/DevToolsActivePort'),'utf8')).split('\n')[0]);
    worker = spawn(process.env.PYTHON || 'python3', [path.join(__dirname, 'panel_runtime_worker.py'),
      `http://127.0.0.1:${port}`, 'http://context-runtime.invalid/', root], {stdio:['pipe','pipe','pipe'],
      env:{...process.env, CODEX_HOME:path.join(root,'home'), QUOTA_ACCOUNT_CLI:cli}});
    const lines = readline.createInterface({input:worker.stdout})[Symbol.asyncIterator]();
    let stderr = ''; worker.stderr.on('data', data => {stderr += data;});
    const step = async () => {
      worker.stdin.write('step\n'); let timer;
      try {
        const result = await Promise.race([lines.next(), new Promise((_,reject) => {timer=setTimeout(()=>reject(Error('worker deadline '+stderr)),15000);})]);
        assert.equal(result.done,false,stderr); assert.equal(JSON.parse(result.value).status,'updated');
      } finally {clearTimeout(timer);}
    };
    const waitFor = async predicate => {
      const deadline = Date.now()+15000;
      while (Date.now()<deadline) {
        await step(); if (await predicate()) return;
        await new Promise(resolve=>setTimeout(resolve,50));
      }
      throw Error('context settings result deadline');
    };
    await step();
    await page.locator('[data-settings-toggle]').click();
    await page.locator('[data-context-defaults] summary').click();
    await page.waitForFunction(()=>window.__quotaMonitorV2ContextDefaultsRequested?.action==='read');
    await waitFor(()=>page.evaluate(()=>window.__quotaMonitorV2Snapshot?.contextDefaults?.status==='ready'));
    assert.equal(await page.locator('[data-context-preset]').inputValue(),'current');
    assert.equal(await page.locator('[data-context-default-action="save"]').isDisabled(),true);
    const unchanged = await fs.readFile(config,'utf8');
    for (const [preset, capacity, threshold] of [['short',128000,96000],['everyday',256000,192000],['long',512000,384000]]) {
      const before = await fs.readFile(config,'utf8');
      await page.locator('[data-context-preset]').selectOption(preset);
      await step();
      assert.equal(await fs.readFile(config,'utf8'),before,'choosing a preset does not save');
      await page.locator('[data-context-default-action="save"]').click();
      await waitFor(()=>page.evaluate(capacity=>window.__quotaMonitorV2Snapshot?.contextDefaults?.feedback==='saved' &&
        window.__quotaMonitorV2Snapshot.contextDefaults.windowTokens===capacity,capacity));
      const saved = await fs.readFile(config,'utf8');
      assert.ok(saved.includes(`model_context_window = ${capacity}`) && saved.includes(`model_auto_compact_token_limit = ${threshold}`));
      assert.equal(await page.locator('[data-context-preset]').inputValue(),'current');
    }
    assert.ok(unchanged.includes('# keep') && !unchanged.includes('model_context_window'));
    await page.locator('[data-context-preset]').selectOption('manual');
    await page.locator('[data-context-window]').fill('180000');
    await page.locator('[data-context-compact]').fill('150000');
    await page.locator('[data-context-default-action="save"]').click();
    await waitFor(()=>page.evaluate(()=>window.__quotaMonitorV2Snapshot?.contextDefaults?.feedback==='saved'));
    assert.match(await fs.readFile(config,'utf8'),/model_context_window = 180000/);
    assert.match(await page.locator('[data-context-default-status]').innerText(),/重启 Codex/);
    assert.equal(await page.locator('[data-context] [role="meter"]').count(),0,'config edits never invent observed context usage');
    await page.locator('[data-context-default-action="reset"]').click();
    await waitFor(()=>page.evaluate(()=>window.__quotaMonitorV2Snapshot?.contextDefaults?.windowTokens===null && window.__quotaMonitorV2Snapshot?.contextDefaults?.feedback==='saved'));
    const after = await fs.readFile(config,'utf8');
    assert.ok(after.includes('# keep') && after.includes('web_search = "disabled"'));
    assert.ok(!after.includes('model_context_window') && !after.includes('model_auto_compact_token_limit'));
    console.log('runtime: current default, three preset saves, manual save/reset -> CDP -> monitor -> real Codex config RPC passed in temporary home');
  } finally {
    if (worker) {
      const stopped = new Promise(resolve => worker.once('exit',resolve));
      worker.stdin.end('stop\n'); let timer;
      await Promise.race([stopped,new Promise(resolve => {timer=setTimeout(()=>{worker.kill('SIGKILL');resolve();},3000);})]);
      clearTimeout(timer);
    }
    if (context) await context.close();
    await fs.rm(root,{recursive:true,force:true});
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
