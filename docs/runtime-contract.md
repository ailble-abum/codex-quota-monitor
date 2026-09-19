# 页面选择与更新循环

2026-09-20，基于 f3c46eb，在独立 V2 推进。仅为显式授权的测试页面提供数值桥，不是已安装监视器或真实 Codex DOM 适配器。

## 范围与选型

复用 V2 CDPClient、SessionJournal、panel_payload，不读取或移植旧 CDP/注入循环源码。HTTP 发现使用 Python 标准库 http.client；已有 websockets==15.0.1 负责 CDP，不增加生产依赖。Playwright 仍仅用于验收。参考 [官方 HTTP endpoint 说明](https://learn.microsoft.com/en-us/microsoft-edge/devtools/protocol/#devtools-protocol-http-endpoints) 的 /json/list 与 [Runtime.evaluate](https://chromedevtools.github.io/devtools-protocol/tot/Runtime/#method-evaluate)。核查日期 2026-09-20：协议文档与隔离 Chromium 实测，不代表宿主应用接口稳定性或发行审计。

没有引入完整浏览器自动化运行时：当前仅需列目标与执行固定表达式，已有通信层足够。未来宿主接入再核对真实任务身份接口，不猜 DOM 结构。

## 使用契约

```python
from quota_monitor.runtime import UpdateLoop

loop = UpdateLoop('http://127.0.0.1:9222', 'about:blank',
                  {'one': '/absolute/synthetic/one.jsonl'})
await loop.run(interval=1)
```

- 调用者明确给出数字回环 HTTP origin、完整页面 URL、任务到日志的映射。无端口扫描、全目录轮询、认证读取或应用启动/重启。
- 页面通过 window.__quotaMonitorV2Thread 显式提供任务 ID；支持 local: 前缀。缺失、null、非字符串或非法 ID 返回 unselected 且不写入快照；有效但未映射的任务仍产生空摘要。此字段是隔离集成协议，不能宣称真实 Codex 已提供它。
- 每步 GET /json/list，精确匹配 type=page 和完整 URL；零目标、多个目标或端点不一致均不写入并关闭当前连接。页面 WS 必须与 HTTP origin 同地址/端口，路径 ID 必须与目标 ID 一致。标题不参与授权。目标列表至多 256 项、响应体至多 1 MiB。
- HTTP 不使用系统代理、不跟随重定向；连接超时 2 秒，连接后的请求由额外 2 秒 socket shutdown 截止约束，避免慢速响应无限占用工作线程。异步取消不会立刻中止标准库线程，但后台请求仍在上述预算内终止；不以取消成功冒充网络请求瞬间结束。
- 唯一目标不变时复用 WS；错误后本步不重发，下一个间隔重新发现、读取、应用当前状态。只有本模块固定的幂等快照表达式允许这种恢复；不能扩展为任意写脚本重试。
- 缓存每个显式文件的增量读取器；身份必须与映射任务一致。未知任务/缺失日志/未读完时下发空摘要。沿用读取器的追加、截断和原子替换契约；不保证检测同 inode 的覆盖后增大等非追加写法。
- 写入前在同一 JS 执行中复核 URL 与任务；切换竞态返回 changed，本步不应用旧任务载荷。没有后台重叠 step；实例是单拥有者，调用者不得同时调用 step/run/close。
- 页面读取 window.__quotaMonitorV2Snapshot 获取投影。getter 在 URL/任务不同或 120 秒期限到达后返回 null；重读日志成功才能产生新期限。仅数值、模型等已有裁剪字段，不传日志正文或文件路径。
- 默认 getter 的过期保护只约束再次读取。后续新增可选 panel=True，页内转发器负责向已有面板主动发送失效清空，见 [宿主与面板契约](host-panel-contract.md)；其他复制快照的消费者仍需处理失效。
- run 在每步结束后等待 interval，再启动下一步；取消向调用方传播，并关闭拥有的 WS。不扫描或关闭其他浏览器/应用。

## 验证与接续

先安装 requirements-cdp.txt，然后运行：

```sh
python -m unittest discover -s tests -q
NODE_PATH=/path/to/existing/node_modules PYTHON=/path/to/python node tools/verify_cdp.cjs
```

本轮 Python 3.9.6 与 3.14.3 各 91 项通过。新增测试覆盖唯一/歧义/端点错配、HTTP 非本机/重定向/格式/大小限制与响应头停滞超时、显式日志身份与增量读取、取消清理。临时 Chromium 使用自动清理的 profile 和合成日志，覆盖实际 run 循环发布与取消关闭、数值读取、连接复用、追加日志、真实 WS 断开与下轮恢复、任务竞态、任务切换与缺失、过期 getter、页面刷新、无匹配目标与多页面歧义。过期通过替换测试页 performance.now 模拟，不是实等 120 秒。

没有访问真实会话或改变现用安装；未完成原生 macOS Codex UI、Windows、安装包、旧面板更新适配及发行来源验收。后续已完成来源核对与隔离页面中的活动任务识别/面板失效清空，见 [接续契约](host-panel-contract.md)；不能把隔离 bridge 当作已替换旧 injector 或原生验收通过。

接续修正：补齐未显式选择任务时的停写边界。临时 Chromium 先复现失败，再验证 undefined/null/数字/空串/非法路径/对象六类输入均不创建快照；刷新后等待 unselected，再由宿主明确选择任务。
