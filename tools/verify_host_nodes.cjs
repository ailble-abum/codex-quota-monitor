const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {chromium, webkit} = require('playwright');
const evidenceDir = process.argv[2] || null;

const assistant = '[data-content-search-assistant-turn-key]';
const chat = '[data-chatgpt-conversation-turn="true"]';
const root = '#codex-context-token-inspector-root';
const turnSelector = `${assistant}, ${chat}`;
const turn = {closest: selector => selector === turnSelector ? turn : null};
const child = {closest: selector => selector === turnSelector ? turn : null};
const own = {closest: selector => selector === turnSelector || selector === root ? own : null};
const fallback = {closest: selector => selector === turnSelector ? fallback : null};
let rows = {[assistant]: [child, turn, own]};
const context = vm.createContext({document: {querySelectorAll: selector => rows[selector] || []}});
vm.runInContext("const ROOT_ID = 'codex-context-token-inspector-root'", context);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../quota_monitor/panel_host_details.js'), 'utf8'), context);
assert.deepEqual(Array.from(context.hostMessageNodes()), [turn]);
rows = {[chat]: [fallback]};
assert.deepEqual(Array.from(context.hostMessageNodes()), [fallback]);
rows = {};
assert.deepEqual(Array.from(context.hostMessageNodes()), []);
const tagged = {dataset: {appActionSidebarThreadId: 'thread-1'}};
assert.equal(context.hostThreadId({matches: () => true, dataset: tagged.dataset}), 'thread-1');
assert.equal(context.hostThreadId({matches: () => false, querySelector: () => tagged}), 'thread-1');
assert.equal(context.hostThreadId({matches: () => false, querySelector: () => null}), null);
const messages = [{textContent: ' first answer '}, {textContent: 'second answer'}];
const details = [{textPrefix: 'first', id: 1}, {textPrefix: 'second', id: 2}];
assert.deepEqual(Array.from(context.hostAssignments(messages, details), item => item.id), [1, 2]);
assert.deepEqual(Array.from(context.hostAssignments([{textContent: 'unknown'}], details), item => item.id), [2]);

async function verifyTooltip(engine) {
  const browser = await engine.launch();
  try {
    const page = await browser.newPage({viewport:{width:220,height:96}});
    page.setDefaultTimeout(5000);
    await page.setContent(`<style>body{margin:0;font:13px system-ui}.shell{position:relative;height:96px}
      [data-app-action-sidebar-thread-row]{position:absolute;left:4px;width:64px;height:24px}
      #top{top:0}#bottom{bottom:0}</style>
      <div class="shell" data-app-shell-active-page="true">
        <button id="top" data-app-action-sidebar-thread-row data-app-action-sidebar-thread-id="one" data-app-action-sidebar-thread-kind="local" data-app-action-sidebar-thread-host-id="local">one</button>
        <button id="other" style="top:32px" data-app-action-sidebar-thread-row data-app-action-sidebar-thread-id="two" data-app-action-sidebar-thread-kind="local" data-app-action-sidebar-thread-host-id="local">two</button>
        <button id="bottom" data-app-action-sidebar-thread-row data-app-action-sidebar-thread-id="one" data-app-action-sidebar-thread-kind="local" data-app-action-sidebar-thread-host-id="local">one</button>
      </div>
      <div data-app-shell-active-page="false">
        <button id="inactive" data-app-action-sidebar-thread-row data-app-action-sidebar-thread-id="one" data-app-action-sidebar-thread-kind="local" data-app-action-sidebar-thread-host-id="local">stale</button>
      </div>`);
    const styles = fs.readFileSync(path.join(__dirname, '../quota_monitor/panel_styles.js'), 'utf8');
    const host = fs.readFileSync(path.join(__dirname, '../quota_monitor/panel_host_details.js'), 'utf8');
    await page.evaluate(({styles, host}) => {
      window.ROOT_ID = 'codex-context-token-inspector-root';
      window.language = 'zh'; window.uiLanguage = () => window.language;
      window.token = value => String(value);
      (0, eval)(styles); (0, eval)(host);
      const style = document.createElement('style'); style.textContent = panelCSS(); document.head.append(style);
      window.testPayload = {summaries:[{thread_id:'one', session_total_tokens:9007199254740991,
        session_input_tokens:123456789012345, session_cached_input_tokens:98765432101234,
        session_output_tokens:76543210987654, session_reasoning_tokens:54321098765432,
        compaction_count:1234567890, post_compaction_tokens:987000, post_compaction_percent:98.7},
        {thread_id:'two', session_total_tokens:222, session_input_tokens:200,
        session_cached_input_tokens:150, session_output_tokens:22, session_reasoning_tokens:11,
        compaction_count:2, post_compaction_tokens:375, post_compaction_percent:37.5}]};
      projectHostDetails(window.testPayload);
    }, {styles, host});
    assert.equal(await page.locator('#inactive').getAttribute('data-cti-v2-sidebar-note'), null,
      'inactive app shell rows must not receive current tooltip data');
    for (const selector of ['#top', '#bottom']) {
      const initialRowBox = await page.locator(selector).boundingBox();
      await page.mouse.move(initialRowBox.x + initialRowBox.width / 2, initialRowBox.y + initialRowBox.height / 2);
      const tip = page.locator('#cti-v2-sidebar-tooltip');
      await tip.waitFor();
      assert.equal(await tip.locator('span').count(), 14);
      const geometry = await tip.evaluate(node => {
        const rect = node.getBoundingClientRect();
        const values = [...node.querySelectorAll('.cti-v2-sidebar-tooltip-value')].map(item => item.getBoundingClientRect());
        const labels = [...node.querySelectorAll('.cti-v2-sidebar-tooltip-label')].map(item => item.getBoundingClientRect());
        return {left:rect.left,top:rect.top,right:rect.right,bottom:rect.bottom,
          clientHeight:node.clientHeight,scrollHeight:node.scrollHeight,
          valueRights:values.map(item => item.right), separated:values.every((item,index) => labels[index].right <= item.left)};
      });
      assert.ok(geometry.left >= 7 && geometry.top >= 7 && geometry.right <= 213 && geometry.bottom <= 89,
        `${selector} tooltip must remain inside the narrow viewport: ${JSON.stringify(geometry)}`);
      assert.ok(geometry.separated, 'label and value columns must not overlap');
      assert.ok(Math.max(...geometry.valueRights) - Math.min(...geometry.valueRights) < 1,
        'numeric values must share a right-aligned column');
      assert.ok(geometry.scrollHeight > geometry.clientHeight, 'short viewport must expose a scrollable tooltip');
      const rowBox = await page.locator(selector).boundingBox();
      const tipBox = await tip.boundingBox();
      await page.mouse.move(rowBox.x + rowBox.width / 2, rowBox.y + rowBox.height / 2);
      await page.mouse.move(tipBox.x + 4, tipBox.y + 4, {steps:12});
      await page.waitForTimeout(160);
      assert.equal(await tip.count(), 1, 'moving from the row into the tooltip must keep it open');
      assert.ok(await tip.evaluate(node => { node.scrollTop = node.scrollHeight; return node.scrollTop > 0; }),
        'tooltip contents must be scrollable to the final row');
      await tip.evaluate(node => { node.__testIdentity = 'preserved'; });
      await page.evaluate(() => projectHostDetails({summaries:[{thread_id:'one', session_total_tokens:9007199254740991,
        session_input_tokens:123456789012345, session_cached_input_tokens:98765432101234,
        session_output_tokens:76543210987654, session_reasoning_tokens:54321098765432,
        compaction_count:1234567890, post_compaction_tokens:987000, post_compaction_percent:98.7}]}));
      assert.equal(await tip.evaluate(node => node.__testIdentity), 'preserved',
        'repeated publishing must preserve the tooltip being read');
      await page.mouse.move(219, 95);
      await page.waitForFunction(() => !document.getElementById('cti-v2-sidebar-tooltip'), null, {timeout:1000});
    }
    await page.evaluate(() => projectHostDetails(window.testPayload));
    await page.mouse.move(36, 44);
    await page.waitForSelector('#cti-v2-sidebar-tooltip');
    const otherText = await page.locator('#cti-v2-sidebar-tooltip').innerText();
    assert.match(otherText, /2 (?:次|times)/, 'second row must use its own compaction count');
    assert.match(otherText, /37\.5%/, 'second row must use its own post-compaction percentage');
    assert.doesNotMatch(otherText, /98\.7%|1234567890/,
      'second row must not reuse the selected conversation health');
    await page.mouse.move(219, 95);
    await page.waitForFunction(() => !document.getElementById('cti-v2-sidebar-tooltip'));
    if (evidenceDir) {
      fs.mkdirSync(evidenceDir, {recursive:true});
      await page.setViewportSize({width:360,height:180});
      const language = engine === chromium ? 'zh' : 'en';
      await page.evaluate(language => { window.language = language; projectHostDetails(window.testPayload); }, language);
      await page.mouse.move(36, 12);
      await page.waitForSelector('#cti-v2-sidebar-tooltip');
      await page.screenshot({path:path.join(evidenceDir,
        engine === chromium ? 'chromium-top-narrow-long-numbers.png' : 'webkit-bottom-narrow-long-numbers.png')});
      await page.mouse.move(359, 179);
      await page.waitForFunction(() => !document.getElementById('cti-v2-sidebar-tooltip'));
    }
    await page.mouse.move(36, 12);
    await page.waitForSelector('#cti-v2-sidebar-tooltip');
    await page.evaluate(() => projectHostDetails({summaries:[]}));
    assert.match(await page.locator('#cti-v2-sidebar-tooltip').innerText(), /读取|Reading/,
      'unloaded logs should replace old values with visible loading feedback');
    assert.equal(await page.evaluate(() => window.__quotaMonitorV2SidebarThread), 'one');
    await page.evaluate(() => projectHostDetails({summaries:[],sidebarStatus:{threadId:'one',
      status:'loading',readBytes:42,totalBytes:100}}));
    assert.match(await page.locator('#cti-v2-sidebar-tooltip').innerText(), /42%/,
      'large journal reads must expose numeric progress');
    await page.evaluate(() => projectHostDetails({summaries:[],sidebarStatus:{threadId:'one',status:'loading'}}));
    assert.ok(!(await page.locator('#cti-v2-sidebar-tooltip').innerText()).includes('%'),
      'a pending unfinished line must not appear as 100% complete');
    await page.evaluate(() => projectHostDetails({summaries:[],sidebarStatus:{threadId:'one',status:'not_found'}}));
    assert.match(await page.locator('#cti-v2-sidebar-tooltip').innerText(), /暂无本机|No local/);
    await page.evaluate(() => projectHostDetails(window.testPayload));
    assert.equal(await page.locator('#cti-v2-sidebar-tooltip span').count(), 14,
      'completed data should populate the same hovered tooltip without another mouse movement');
    await page.evaluate(() => projectHostDetails({summaries:[{thread_id:'one', session_total_tokens:1,
      session_input_tokens:1, session_cached_input_tokens:0, session_output_tokens:0,
      session_reasoning_tokens:0, compaction_count:1, post_compaction_tokens:null,
      post_compaction_percent:null}]}));
    let pendingText = await page.locator('#cti-v2-sidebar-tooltip').innerText();
    assert.match(pendingText, /等待首次请求|Waiting for first request/);
    assert.doesNotMatch(pendingText, /压后首请求\s+0(?:\.0)?%|First after compaction\s+0(?:\.0)?%/,
      'a pending real request must not be rendered as zero percent');
    await page.evaluate(() => projectHostDetails({summaries:[{thread_id:'one', session_total_tokens:1,
      session_input_tokens:1, session_cached_input_tokens:0, session_output_tokens:0,
      session_reasoning_tokens:0, compaction_count:1, post_compaction_tokens:400,
      post_compaction_percent:null}]}));
    pendingText = await page.locator('#cti-v2-sidebar-tooltip').innerText();
    assert.match(pendingText, /暂无占比|Percentage unavailable/,
      'known post-compaction tokens without a context window are unavailable, not pending');
    await page.evaluate(() => projectHostDetails({summaries:[{thread_id:'one', session_total_tokens:1,
      session_input_tokens:1, session_cached_input_tokens:0, session_output_tokens:0,
      session_reasoning_tokens:0, compaction_count:0, post_compaction_tokens:null,
      post_compaction_percent:null}]}));
    pendingText = await page.locator('#cti-v2-sidebar-tooltip').innerText();
    assert.match(pendingText, /0 (?:次|times)/, 'zero compactions must remain explicit');
    assert.match(pendingText, /尚未压缩|No compaction yet/);
    await page.mouse.move(page.viewportSize().width - 1, page.viewportSize().height - 1);
    await page.waitForFunction(() => !document.getElementById('cti-v2-sidebar-tooltip'));
    await page.evaluate(() => projectHostDetails({summaries:[]}));
    await page.mouse.move(36, 12);
    await page.waitForSelector('#cti-v2-sidebar-tooltip');
    assert.match(await page.locator('#cti-v2-sidebar-tooltip').innerText(), /读取|Reading/,
      'rows without any prior plugin data must still request and show loading');
    await page.evaluate(() => clearHostProjection());
    assert.equal(await page.locator('#cti-v2-sidebar-tooltip').count(), 0,
      'clearing the plugin must remove the tooltip and hover request');
    assert.equal(await page.evaluate(() => window.__quotaMonitorV2SidebarThread), undefined);
    await page.mouse.move(page.viewportSize().width - 1, page.viewportSize().height - 1);
    await page.mouse.move(36, 12);
    await page.waitForSelector('#cti-v2-sidebar-tooltip');
    assert.match(await page.locator('#cti-v2-sidebar-tooltip').innerText(), /请先打开|Open a local/,
      'without a selected local conversation, do not promise that a log read is running');
    await page.evaluate(() => projectHostDetails({activeThreadId:'one', summaries:[],
      sidebarStatus:{threadId:'one',status:'index_wait'}}));
    assert.match(await page.locator('#cti-v2-sidebar-tooltip').innerText(), /会话列表更新|Conversation list updating/);
    await page.evaluate(() => clearHostProjection());
    for (const [kind, host] of [[null, 'local'], ['local', null], ['cloud', 'local'], ['local', 'remote']]) {
      await page.evaluate(({kind, host}) => {
        const row = document.getElementById('top');
        for (const [name, value] of [['kind', kind], ['host-id', host]]) {
          const attr = 'data-app-action-sidebar-thread-' + name;
          if (value === null) row.removeAttribute(attr); else row.setAttribute(attr, value);
        }
        projectHostDetails(window.testPayload);
        row.dispatchEvent(new MouseEvent('mouseover', {bubbles:true}));
      }, {kind, host});
      assert.equal(await page.locator('#top').getAttribute('data-cti-v2-sidebar-note'), null,
        'unknown or remote rows must not receive local usage data');
      assert.equal(await page.locator('#cti-v2-sidebar-tooltip').count(), 0);
      assert.equal(await page.evaluate(() => window.__quotaMonitorV2SidebarThread), undefined);
    }
    console.log(`${engine.name()}: tooltip grid, narrow bounds, scrolling, hover retention and inactive-shell filtering passed`);
  } finally {
    await browser.close();
  }
}

(async () => {
  console.log('host message selection: deduplication, fallback and own-root exclusion passed');
  for (const engine of [chromium, webkit]) await verifyTooltip(engine);
})().catch(error => { console.error(error); process.exitCode = 1; });
