// Real CDP loop -> synthetic journals -> external panel, isolated Chromium only.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { spawn, execFileSync } = require('node:child_process');
const { once } = require('node:events');
const readline = require('node:readline');
const { chromium } = require('playwright');

async function main() {
  const [legacyScripts, artifacts] = process.argv.slice(2);
  assert.ok(legacyScripts && artifacts, 'Usage: verify_runtime_panel.cjs LEGACY_SCRIPTS ARTIFACT_DIR');
  const python = process.env.PYTHON || 'python3';
  const fixture = JSON.parse(execFileSync(python,
    [path.join(__dirname, 'panel_fixture.py'), legacyScripts], {encoding: 'utf8', maxBuffer: 32 * 1024 * 1024}));
  await fs.mkdir(artifacts, {recursive: true});
  for (const colorScheme of ['light', 'dark']) {
    const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'quota-runtime-panel-'));
    let context, worker, lines, exited;
    try {
      for (const [key, count, total] of [['one', 250, 700], ['two', 500, 900]]) {
        const rows = [{type: 'session_meta', payload: {id: key}},
          {type: 'event_msg', payload: {type: 'token_count', info: {
            last_token_usage: {input_tokens: count}, total_token_usage: {total_tokens: total},
            model_context_window: 1000}}}];
        await fs.writeFile(path.join(temp, `${key}.jsonl`), rows.map(JSON.stringify).join('\n') + '\n');
      }
      context = await chromium.launchPersistentContext(path.join(temp, 'profile'), {
        headless: true, colorScheme, viewport: {width: 1280, height: 800},
        args: ['--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0']});
      const unexpected = [], errors = [];
      await context.route('**/*', route => {
        if (route.request().url() !== 'http://panel.invalid/') {
          unexpected.push(route.request().url());
          return route.abort();
        }
        return route.fulfill({contentType: 'text/html; charset=utf-8', body: `<!doctype html><html lang="zh-CN">
          <style>:root{color-scheme:light dark}body{background:Canvas;color:CanvasText;font:16px system-ui;padding:32px}</style>
          <h1>V2 更新循环 → 现有面板</h1><p>合成会话 · 独立 CDP · 隔离验收</p>
          <button data-app-action-sidebar-thread-row data-app-action-sidebar-thread-kind="local" data-app-action-sidebar-thread-host-id="local" data-app-action-sidebar-thread-id="one" data-app-action-sidebar-thread-active="true">任务一</button>
          <button data-app-action-sidebar-thread-row data-app-action-sidebar-thread-kind="local" data-app-action-sidebar-thread-host-id="local" data-app-action-sidebar-thread-id="two" data-app-action-sidebar-thread-active="false">任务二</button>
          <button data-app-action-sidebar-thread-row data-app-action-sidebar-thread-kind="local" data-app-action-sidebar-thread-host-id="local" data-app-action-sidebar-thread-id="missing" data-app-action-sidebar-thread-active="false">无记录</button></html>`});
      });
      const page = context.pages()[0];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto('http://panel.invalid/');
      const port = Number((await fs.readFile(path.join(temp, 'profile/DevToolsActivePort'), 'utf8')).split('\n')[0]);
      worker = spawn(python, [path.join(__dirname, 'panel_runtime_worker.py'),
        `http://127.0.0.1:${port}`, 'http://panel.invalid/', temp], {stdio: ['pipe', 'pipe', 'pipe']});
      exited = once(worker, 'exit');
      let stderr = '';
      worker.stderr.on('data', data => { stderr += data; });
      lines = readline.createInterface({input: worker.stdout})[Symbol.asyncIterator]();
      const step = async () => {
        worker.stdin.write('step\n');
        let timer;
        try {
          const line = await Promise.race([lines.next(), new Promise((_, reject) => {
            timer = setTimeout(() => reject(Error('worker deadline')), 10000);
          })]);
          assert.equal(line.done, false, stderr);
          return JSON.parse(line.value).status;
        } finally { clearTimeout(timer); }
      };
      const select = key => page.evaluate(key => {
        document.querySelectorAll('[data-app-action-sidebar-thread-row]').forEach(row => {
          row.setAttribute('data-app-action-sidebar-thread-active', String(row.getAttribute('data-app-action-sidebar-thread-id') === key));
        });
      }, key);
      const mount = () => page.evaluate(({script, payload}) => {
        localStorage.setItem('cti-language', 'zh');
        localStorage.setItem('cti-layout-v2', JSON.stringify({expanded: {edge: 'right', y: 120}}));
        (0, eval)(script)(payload);
      }, {script: fixture.script, payload: fixture.payloads.missing});
      const meter = value => page.waitForFunction(value =>
        document.querySelector('[data-context] [role="meter"]')?.getAttribute('aria-valuenow') === String(value), value);
      const empty = () => page.waitForFunction(() =>
        !document.querySelector('[data-context] [role="meter"]') && document.querySelector('[data-metrics]')?.textContent === '');
      await mount();
      await select('one');
      assert.equal(await step(), 'updated');
      await meter(25);
      await fs.appendFile(path.join(temp, 'one.jsonl'), JSON.stringify({type: 'event_msg', payload: {
        type: 'token_count', info: {last_token_usage: {input_tokens: 350}, model_context_window: 1000}}}) + '\n');
      assert.equal(await step(), 'updated');
      await meter(35);
      await page.evaluate(() => window.__quotaMonitorV2Delivery.stop());
      await select(null);
      assert.equal(await step(), 'unselected');
      await empty(); // Runtime must invalidate even when the page timer stopped.
      await select('two');
      await empty();
      assert.equal(await step(), 'updated');
      await meter(50);
      await page.locator('.cti-edge-mascot').focus();
      await page.locator('[data-details] summary').click();
      assert.match(await page.locator('[data-metrics]').innerText(), /900/);
      await page.locator('.cti-edge-mascot img').evaluate(img => img.decode());
      await page.screenshot({path: path.join(artifacts, `runtime-${colorScheme}.png`)});
      await select('missing');
      assert.equal(await step(), 'updated');
      await empty();
      await select('one');
      assert.equal(await step(), 'updated');
      await meter(35);
      // No Python update or manual consumer call: page-side lease must clear DOM.
      await page.evaluate(() => { performance.now = () => 1e15; });
      await empty();
      await page.evaluate(() => { delete performance.now; });
      assert.equal(await step(), 'updated');
      await meter(35);
      await page.reload();
      await select('two');
      assert.equal(await step(), 'javascript_error'); // Renderer intentionally absent after reload.
      await mount();
      assert.equal(await step(), 'updated');
      await meter(50);
      assert.equal(await step(), 'updated');
      assert.equal(await page.locator('.cti-hud').count(), 1);
      assert.equal(await page.locator('.cti-edge-mascot').count(), 1);
      assert.deepEqual(errors, []);
      assert.deepEqual(unexpected, []);
      console.log(`Chromium ${colorScheme}: real CDP, append, switch, missing, autonomous expiry clear, reload, singleton passed`);
      worker.stdin.end('stop\n');
      const [code] = await exited;
      assert.equal(code, 0, stderr);
    } finally {
      if (worker && worker.exitCode === null) { worker.kill(); await exited; }
      if (context) await context.close();
      await fs.rm(temp, {recursive: true, force: true});
    }
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
