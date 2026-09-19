// Own temporary browser/profile only; never discover an installed Codex target.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { execFile } = require('node:child_process');
const { promisify } = require('node:util');
const { chromium } = require('playwright');

async function main() {
  const profile = await fs.mkdtemp(path.join(os.tmpdir(), 'quota-cdp-browser-'));
  let context;
  try {
    context = await chromium.launchPersistentContext(profile, {
      headless: true, args: ['--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0']
    });
    await context.route('**/*', route => route.abort());
    const page = context.pages()[0];
    await page.setContent('<title>isolated CDP probe</title><p>Synthetic page only</p>');
    const port = Number((await fs.readFile(path.join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]);
    assert.ok(Number.isInteger(port) && port > 0 && port <= 65535);
    const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`, { redirect: 'error' })).json();
    const matches = targets.filter(target => target.type === 'page' && target.title === 'isolated CDP probe');
    assert.equal(matches.length, 1);
    const { stdout } = await promisify(execFile)(process.env.PYTHON || 'python3',
      [path.join(__dirname, 'cdp_probe.py'), matches[0].webSocketDebuggerUrl], { timeout: 15000 });
    process.stdout.write(stdout);
    const runtime = await promisify(execFile)(process.env.PYTHON || 'python3',
      [path.join(__dirname, 'runtime_probe.py'), `http://127.0.0.1:${port}`], { timeout: 20000 });
    process.stdout.write(runtime.stdout);
    await context.newPage();
    const ambiguous = await promisify(execFile)(process.env.PYTHON || 'python3',
      [path.join(__dirname, 'runtime_probe.py'), `http://127.0.0.1:${port}`, 'ambiguous'], { timeout: 10000 });
    process.stdout.write(ambiguous.stdout);
  } finally {
    if (context) await context.close();
    // Only the exact profile allocated by this invocation is removed.
    await fs.rm(profile, { recursive: true, force: true });
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
