// Production CLI subprocess, temporary Chromium/profile/journal only.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const readline = require('node:readline');
const {spawn} = require('node:child_process');
const {chromium} = require('playwright');

async function until(predicate) {
  const end = Date.now() + 8000;
  while (!predicate()) {
    if (Date.now() > end) throw Error('CLI probe deadline');
    await new Promise(resolve => setTimeout(resolve, 25));
  }
}
async function main() {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'quota-live-cli-'));
  let context;
  const children = [];
  try {
    context = await chromium.launchPersistentContext(path.join(directory, 'profile'), {
      headless: true, args: ['--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0']});
    await context.route('**/*', route => route.abort());
    const page = context.pages()[0];
    const mount = () => page.evaluate(() => {
      document.body.innerHTML = '<output></output>';
      window.__quotaMonitorV2Thread = 'one';
      window.__codexContextTokenInspectorUpdate = payload => {
        document.querySelector('output').textContent = payload.summaries[0]?.latest_context_tokens ?? '';
      };
    });
    await fs.writeFile(path.join(directory, 'one.jsonl'), [
      {type: 'session_meta', payload: {id: 'one'}},
      {type: 'event_msg', payload: {type: 'token_count', info: {
        last_token_usage: {input_tokens: 250}, model_context_window: 1000}}}
    ].map(JSON.stringify).join('\n') + '\n');
    const port = Number((await fs.readFile(path.join(directory, 'profile/DevToolsActivePort'), 'utf8')).split('\n')[0]);
    const config = path.join(directory, 'config.json');
    await fs.writeFile(config, JSON.stringify({origin: `http://127.0.0.1:${port}`, page_url: 'about:blank',
      journals: {one: 'one.jsonl'}, panel: true}));
    function start(extra = []) {
      const proc = spawn(process.env.PYTHON || 'python3', ['-m', 'quota_monitor.live', '--config', config,
        '--interval', '0.1', '--max-failures', '3', ...extra], {cwd: path.join(__dirname, '..'), stdio: ['ignore', 'pipe', 'pipe']});
      children.push(proc);
      const rows = [];
      let stderr = '';
      readline.createInterface({input: proc.stdout}).on('line', line => rows.push(JSON.parse(line)));
      proc.stderr.on('data', chunk => { stderr += chunk; });
      return {proc, rows, stderr: () => stderr};
    }
    for (const sig of ['SIGINT', 'SIGTERM']) {
      await mount();
      const run = start();
      await until(() => run.rows.some(row => row.status === 'updated'));
      await page.waitForFunction(() => document.querySelector('output').textContent === '250');
      await page.reload();
      await until(() => run.rows.some(row => row.status === 'unselected'));
      await mount();
      await page.waitForFunction(() => document.querySelector('output').textContent === '250');
      run.proc.kill(sig);
      await until(() => run.proc.exitCode !== null);
      assert.equal(run.proc.exitCode, sig === 'SIGINT' ? 130 : 143, run.stderr());
      assert.deepEqual(run.rows.at(-1), {event: 'stopped', reason: sig.toLowerCase(), cleanup: 'released'});
      assert.equal(await page.locator('output').textContent(), '');
      assert.equal(await page.evaluate(() => Object.hasOwn(window, '__quotaMonitorV2Snapshot')), false);
      assert.equal(await page.evaluate(() => Object.hasOwn(window, '__quotaMonitorV2Delivery')), false);
      assert.equal(run.stderr(), '');
      assert.ok(!JSON.stringify(run.rows).includes(directory));
    }
    await mount();
    const once = start(['--once']);
    await until(() => once.proc.exitCode !== null);
    assert.equal(once.proc.exitCode, 0, once.stderr());
    assert.deepEqual(once.rows.map(row => row.event), ['state', 'stopped']);
    assert.equal(once.rows.at(-1).cleanup, 'released');
    assert.equal(await page.locator('output').textContent(), '');

    await fs.mkdir(path.join(directory, 'sessions'));
    await fs.copyFile(path.join(directory, 'one.jsonl'), path.join(directory, 'sessions/random.jsonl'));
    await fs.writeFile(config, JSON.stringify({origin: `http://127.0.0.1:${port}`, page_url: 'about:blank',
      session_root: 'sessions', panel: true}));
    await mount();
    const indexed = start();
    await until(() => indexed.rows.some(row => row.status === 'updated'));
    await page.waitForFunction(() => document.querySelector('output').textContent === '250');
    await fs.copyFile(path.join(directory, 'one.jsonl'), path.join(directory, 'sessions/duplicate.jsonl'));
    await until(() => indexed.rows.some(row => row.status === 'data_index_wait'));
    await page.waitForFunction(() => document.querySelector('output').textContent === '');
    await new Promise(resolve => setTimeout(resolve, 600));
    assert.equal(indexed.proc.exitCode, null, indexed.stderr());
    indexed.proc.kill('SIGTERM');
    await until(() => indexed.proc.exitCode !== null);
    assert.equal(indexed.proc.exitCode, 143, indexed.stderr());
    // SIGTERM can interrupt a CDP exchange; that intentionally closes the socket.
    assert.ok(['released', 'lease_pending'].includes(indexed.rows.at(-1).cleanup));
    assert.equal(await page.locator('output').textContent(), '');
    assert.equal(indexed.stderr(), '');
    const ambiguousOnce = start(['--once']);
    await until(() => ambiguousOnce.proc.exitCode !== null);
    assert.equal(ambiguousOnce.proc.exitCode, 2, ambiguousOnce.stderr());
    assert.equal(ambiguousOnce.rows[0].status, 'data_ambiguous');
    assert.equal(ambiguousOnce.rows.at(-1).cleanup, 'released');
    await fs.unlink(path.join(directory, 'sessions/duplicate.jsonl'));

    await mount();
    const closed = start();
    await until(() => closed.rows.some(row => row.status === 'updated'));
    await context.close();
    context = null;
    await until(() => closed.proc.exitCode !== null);
    assert.equal(closed.proc.exitCode, 2, closed.stderr());
    assert.equal(closed.rows.at(-1).reason, 'failure_limit');
    assert.equal(closed.rows.at(-1).cleanup, 'lease_pending');
    assert.equal(closed.rows.filter(row => row.status === 'discovery_unavailable').length, 1);
    console.log('live CLI Chromium: relative config, values, reload recovery, SIGINT/SIGTERM release, once, host exit, directory association/invalidation and quiet failure limit passed');
  } finally {
    for (const proc of children) {
      if (proc.exitCode === null && proc.signalCode === null) {
        proc.kill('SIGKILL');
        await until(() => proc.exitCode !== null || proc.signalCode !== null);
      }
    }
    if (context) await context.close();
    await fs.rm(directory, {recursive: true, force: true});
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
