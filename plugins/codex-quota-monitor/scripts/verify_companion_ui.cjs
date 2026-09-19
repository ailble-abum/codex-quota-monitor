const { chromium, webkit } = require('playwright');
const { execFileSync } = require('node:child_process');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const scripts = __dirname;
const out = '/tmp/companion-qa';
fs.mkdirSync(out, { recursive: true });
const injection = execFileSync(process.env.PYTHON || 'python3', ['-c', 'from context_token_injector import INJECTION_SCRIPT; print(INJECTION_SCRIPT)'], {
  cwd: scripts, encoding: 'utf8', maxBuffer: 16 * 1024 * 1024,
});

function summary(thread, ctx) {
  return {
    thread_id: thread,
    thread_keys: [thread, `local:${thread}`],
    latest_context_percent: ctx,
    latest_context_tokens: Math.round(200000 * ctx / 100),
    context_window: 200000,
    latest_turn_total_tokens: 1200,
    latest_turn_input_tokens: 1000,
    latest_turn_cached_input_tokens: 600,
    latest_turn_output_tokens: 200,
    session_total_tokens: 20000,
    model: 'fixture-model', reasoning_effort: 'fixture',
  };
}

function payload(remaining, ctx = 20, thread = 'a') {
  return {
    activeThreadId: thread,
    selectedThreadId: thread,
    summaries: [summary('a', thread === 'a' ? ctx : 86), summary('b', thread === 'b' ? ctx : 20)],
    quota: {
      status: 'live', updatedAt: Date.now() / 1000, accountKey: 'fixture-account', planType: 'fixture',
      ordinaryUsageAllowed: remaining > 0, rateLimitReachedType: remaining <= 0 ? 'weekly' : null,
      windows: [{ id: 'short', windowMinutes: 300, resetsAt: 2000000000, remaining, label: '5h' },
                { id: 'weekly', windowMinutes: 10080, resetsAt: 2000600000, remaining: Math.max(remaining, 40), label: 'Weekly' }],
    },
    health: { count: 0, latestAt: null, recommendHandoff: false },
    healthThreadId: 'a',
    observedAt: Date.now() / 1000,
    dom: { sidebarRows: 2, activeRow: true, conversationId: thread },
    build: { pluginVersion: 'fixture', runtimeVersion: 999 },
  };
}

async function run(engine) {
  const name = engine.name();
  const browser = await engine.launch({ headless: true });
  const errors = [];
  const consoleErrors = [];
  const issues = [];
  try {
    const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'zh-CN', colorScheme: 'light', reducedMotion: 'no-preference' });
    const page = await context.newPage();
    page.on('pageerror', e => errors.push(e.stack || e.message));
    page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });
    await page.route('http://companion.test/**', route => route.fulfill({
      contentType: 'text/html',
      body: '<!doctype html><html lang="zh-CN"><style>:root{color-scheme:light dark}body{margin:0;background:Canvas;color:CanvasText}</style><body><nav><button data-app-action-sidebar-thread-row data-app-action-sidebar-thread-active="true" data-app-action-sidebar-thread-id="a">A</button><button data-app-action-sidebar-thread-row data-app-action-sidebar-thread-active="false" data-app-action-sidebar-thread-id="b">B</button></nav></body></html>',
    }));
    await page.goto('http://companion.test/');
    await page.evaluate(() => {
      localStorage.setItem('cti-language', 'zh');
      localStorage.removeItem('cti-companion-state');
      localStorage.setItem('cti-layout-v2', JSON.stringify({ compact: { edge: 'left', y: 150 }, expanded: { edge: 'left', y: 150 } }));
    });
    await page.evaluate(`(${injection})(${JSON.stringify(payload(50))})`);
    await page.locator('.cti-edge-mascot img').evaluate(img => img.decode());
    const update = p => page.evaluate(p => window.__codexContextTokenInspectorUpdate(p), p);
    const state = () => page.evaluate(() => {
      const root = document.querySelector('.cti-hud');
      const mascot = document.querySelector('.cti-edge-mascot');
      const hint = document.querySelector('#cti-context-hint');
      const art = mascot?.querySelector('.cti-mascot-art');
      return { mood: mascot?.dataset.mood, reaction: mascot?.dataset.reaction || null, hint: hint?.textContent || null,
        pinned: root?.dataset.dockPinned, revealed: root?.dataset.revealed, top: mascot?.getBoundingClientRect().top,
        expression: mascot?.dataset.expression, src: mascot?.querySelector('img')?.src,
        width: mascot?.getBoundingClientRect().width, height: mascot?.getBoundingClientRect().height,
        animation: art ? getComputedStyle(art).animationName : null, layout: localStorage.getItem('cti-layout-v2') };
    });
    const idle = await state(); assert.equal(idle.top, 150); assert.equal(idle.expression, 'idle');
    const expressionSources = new Set([idle.src]);
    const expressionFrames = { idle: idle.src };

    for (const [remaining, text, mood] of [[20, '额度剩余不多了', 'concerned'], [10, '额度已低于或等于 10%', 'concerned'], [0, '额度已达上限', 'waiting'], [80, '已确认额度恢复', 'idle']]) {
      await update(payload(remaining));
      await page.waitForTimeout(40);
      const s = await state();
      assert.ok(s.hint?.includes(text), `${name} quota ${remaining}: ${JSON.stringify(s)}`);
      assert.equal(s.mood, mood);
      assert.equal(s.width, idle.width); assert.equal(s.height, idle.height);
      if (remaining === 80) assert.equal(s.expression, 'happy'); else assert.equal(s.expression, 'notice');
      expressionSources.add(s.src);
      expressionFrames[s.expression] = s.src;
      await page.screenshot({ path: path.join(out, `${name}-quota-${remaining}.png`) });
      if (remaining === 20 || remaining === 0) {
        await page.waitForTimeout(950);
        const persistent = await state();
        assert.equal(persistent.expression, remaining === 20 ? 'concerned' : 'waiting');
        assert.equal(persistent.width, idle.width); assert.equal(persistent.height, idle.height);
        expressionSources.add(persistent.src);
        expressionFrames[persistent.expression] = persistent.src;
      }
    }

    await update(payload(80, 86, 'a'));
    await page.waitForTimeout(40);
    assert.ok((await state()).hint?.includes('当前聊天上下文偏高'));
    await page.screenshot({ path: path.join(out, `${name}-ctx-86.png`) });
    await update(payload(80, 96, 'a'));
    await page.waitForTimeout(40);
    assert.ok((await state()).hint?.includes('当前聊天上下文接近窗口上限'));
    await page.screenshot({ path: path.join(out, `${name}-ctx-96.png`) });

    const healthA = payload(80, 96, 'a');
    healthA.health = { count: 2, latestAt: 'fixture-compression-a', recommendHandoff: true, reason: 'baseline', after: 90000, afterPercent: 45 };
    await update(healthA);
    await page.waitForTimeout(40);
    assert.ok((await state()).hint?.includes('已观察到上下文压缩'));

    await page.evaluate(() => {
      const a = document.querySelector('[data-app-action-sidebar-thread-id="a"]');
      const b = document.querySelector('[data-app-action-sidebar-thread-id="b"]');
      a.dataset.appActionSidebarThreadActive = 'false';
      b.dataset.appActionSidebarThreadActive = 'true';
    });
    await page.waitForTimeout(160);
    assert.equal((await state()).hint, null, `${name}: task switch must clear old hint`);
    const healthText = await page.locator('[data-health]').innerText();
    assert.ok(healthText.includes('尚未观察到压缩事件'), `${name}: A health leaked into B: ${healthText}`);
    const stale = payload(80, 96, 'b');
    stale.observedAt = Date.now() / 1000 - 121;
    await update(stale);
    await page.waitForTimeout(40);
    assert.equal(await page.locator('[data-context] [role="meter"]').count(), 0);
    assert.equal(await page.locator('[data-context-ring]').getAttribute('data-tone'), 'unknown');
    await update(payload(80, 20, 'b'));
    await page.waitForTimeout(40);

    const mascot = page.locator('.cti-edge-mascot');
    await mascot.evaluate(el => el.click());
    let s = await state();
    assert.equal(s.pinned, 'true'); assert.equal(s.revealed, 'true');
    await mascot.evaluate(el => el.click());
    assert.equal((await state()).pinned, 'false');
    await page.mouse.move(600, 600);
    await page.waitForTimeout(650);

    let box = await mascot.boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height * 0.25);
    await page.waitForTimeout(50);
    box = await mascot.boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height * 0.25);
    await page.mouse.down();
    await page.waitForTimeout(390);
    const hold = await page.evaluate(() => { const m = document.querySelector('.cti-edge-mascot'), r=m.getBoundingClientRect(); return { reaction:m?.dataset.reaction, motion:m?.dataset.motion, motionSetting:localStorage.getItem('cti-companion-motion'), gesture:m?.__ctiGesture, rect:{x:r.x,y:r.y,width:r.width,height:r.height}, root:document.querySelector('.cti-hud')?.dataset, hit:document.elementFromPoint(r.left + r.width/2, r.top + r.height*.25)?.outerHTML?.slice(0,200) }; });
    assert.equal(hold.gesture?.mode, 'pet', `${name}: 350ms head hold not recognized ${JSON.stringify(hold)}`);
    assert.equal(hold.reaction, 'pet');
    assert.equal(await mascot.getAttribute('data-expression'), 'pet');
    expressionSources.add(await mascot.locator('img').getAttribute('src'));
    expressionFrames.pet = await mascot.locator('img').getAttribute('src');
    await page.mouse.up();

    box = await mascot.boundingBox();
    const startTop = box.y;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height * 0.82);
    await page.waitForTimeout(50);
    box = await mascot.boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height * 0.82);
    await page.mouse.down(); await page.mouse.move(box.x + box.width / 2, box.y + box.height * 0.82 + 80, { steps: 8 }); await page.mouse.up();
    await page.waitForTimeout(30);
    s = await state();
    assert.ok(s.top > startTop + 60, `${name}: body drag did not move: ${startTop} -> ${s.top}`);
    assert.ok(JSON.parse(s.layout).expanded.y > 210, `${name}: drag not persisted: ${s.layout}`);
    await page.screenshot({ path: path.join(out, `${name}-dragged.png`) });

    for (const scheme of ['light', 'dark']) {
      await page.emulateMedia({ colorScheme: scheme, reducedMotion: 'no-preference' });
      await page.screenshot({ path: path.join(out, `${name}-${scheme}.png`) });
    }
    assert.ok(expressionSources.size >= 6, `${name}: expression srcs did not switch: ${expressionSources.size} ${JSON.stringify(Object.fromEntries(Object.entries(expressionFrames).map(([k,v])=>[k,v?.length])))}`);
    await page.evaluate(() => { localStorage.setItem('cti-mascot-scale','2'); window.dispatchEvent(new Event('resize')); });
    await page.waitForTimeout(50);
    assert.ok(Math.abs((await state()).height - idle.height * 2) < 1);
    await page.screenshot({ path: path.join(out, `${name}-2x-dark.png`) });
    await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
    await mascot.hover();
    assert.equal((await state()).animation, 'none', `${name}: reduced motion animation`);
    await page.screenshot({ path: path.join(out, `${name}-reduced-motion.png`) });
    const runtimeErrors = errors;
    assert.deepEqual(runtimeErrors, [], `${name} page errors`);
    assert.deepEqual(consoleErrors, [], `${name} console errors`);
    const final = await state();
    final.src = `${final.src?.slice(0, 24)}… (${final.src?.length || 0} chars)`;
    return { engine: name, errors: runtimeErrors, consoleErrors, issues, final };
  } finally { await browser.close(); }
}

(async () => {
  const results = [];
  for (const engine of [chromium, webkit]) {
    try { results.push(await run(engine)); }
    catch (error) { results.push({ engine: engine.name(), failure: error.stack || String(error) }); }
  }
  fs.writeFileSync(path.join(out, 'results.json'), JSON.stringify(results, null, 2));
  console.log(JSON.stringify(results, null, 2));
  if (results.some(r => r.failure)) process.exitCode = 1;
})();
