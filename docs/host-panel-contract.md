# 宿主活动任务与面板更新桥

2026-09-20，独立 V2，接续 1565580。先以 d3f6bd5 修正无有效任务仍写入快照的问题，再接入现有消费者。没有改变现用安装、真实会话或账户认证。

## 来源核对与复用决定

- 保留 V2 CDPClient、显式回环目标选择、SessionJournal 与 panel_payload。新增 page_bridge.js 只实现标识读取、数值转发和失效清空；没有读取或改写旧宿主定位/更新循环函数。
- [官方 App Server 文档](https://learn.chatgpt.com/docs/app-server) 提供 thread/read 等任务数据接口；本轮需要的是特定桌面页面的活动任务，不能用某个任务存在或运行中替代当前页面选中状态。因此本轮不另启 app-server，也不引入新的生产依赖。
- 本机实际宿主是 /Applications/ChatGPT.app，Bundle ID com.openai.codex，版本 26.908.70816，Build 9275。只读检查 Contents/Resources/app.asar 中的前端资源，未运行或复制其函数。以下是版本内接口证据，不是官方公开稳定 DOM API 承诺。
- webview/assets/app-initial-4d7ea7f81c2d.js 定义 data-app-action-sidebar-thread-row/id/active/kind/host-id；属性构造将 active 转为字符串，与 selected 分开。
- 完整核对链：app-primary 的行包装器取 xSe({locationId, threadKey}) 作为 isActive，经 g8t → _8t 传到属性构造。xSe 是 app-initial 导出的 cjt（内部 u1n）；它通过 l1n 比较 qk 与规范化 threadKey，并检查 pinned-tab 与 sidebarThreadLocationId。qk 来自路由 pathname：本地/待创建本地/远程任务生成对应 key；home、new-thread-panel、chatgpt-thread 和 other 返回 null。由此确认 active 不是侧栏多选 selected 的别名。
- 源文件 SHA-256：app-initial 为 5dcf4a29db25b086f9bd11d053eec60cf0c50bfd988494969cec452e03f19245；app-primary 为 6d75ae321771510842fbcc303846913f7434bc8a67e0c69fb5adb22c632eb3ac。版本变化需重新核对。
- 现有面板继续作为外部旧消费者使用，测试固定于 2705f32a6f080ee1bdbecdc5b43f5fe0f9045eed。仅在独立临时目录提取四个源码文件，由已有 panel_fixture.py 静态读取字面量，不 import/exec 旧 Python，也未将面板或素材复制进 V2。旧归因和许可保留。

## 调用与行为

```python
loop = UpdateLoop(explicit_local_origin, exact_page_url, explicit_journal_paths,
                  host='codex-sidebar', panel=True)
await loop.run(interval=1)
```

- 默认 host='explicit' 保持原合成字段 __quotaMonitorV2Thread 协议；codex-sidebar 模式不会回退到这个字段或任意标题/正文匹配。
- codex-sidebar 只接受恰好一个 active="true" 的 sidebar-thread-row，且 kind="local"、host-id="local"。id 支持 local: 前缀；空值、非法字符、远程 host、云任务及多行歧义都返回 unselected，不下发新数据。缺少/折叠未渲染行时也不猜测；当前模式可能漏报，但不会靠第一条侧栏记录补足。
- 本机任务 ID 仍须与显式映射日志中的 session_meta 一致。待创建任务的别名若与日志不同，本轮会清空摘要；没有绕过身份核验。完整 URL 必须仍等于配置值，SPA 路由变更也不自动扩大目标授权。
- 读取任务与发布快照使用同一份独立 JS，并在实际写入的 JS 执行内再次核对 URL 和任务。参数使用 JSON 序列化；正文不参与表达式拼接。
- panel=True 只调用已存在的 __codexContextTokenInspectorUpdate；不负责安装旧 renderer。hook 缺失或抛错会报 javascript_error 并由现有 CDP 逻辑关闭连接；重新挂载消费者后下一轮可恢复。
- 页面有一个 250ms 的转发定时器。任务改变、URL 改变或 120 秒租期到期时，快照永久失效并向消费者发送空摘要，随后停表；任务切回也不会复活旧快照。下一次真实日志轮询可建立新快照。
- 新转发器首次交付并建立定时器成功后才停止上一只定时器；初始化失败保留旧机制。重复安装保持单一定时器；同一快照不会反复转发。消费者 hook 被替换时会重新转发；读取宿主/时钟失败使快照失效；hook 缺失/抛错时停止定时器并尝试经最后成功的消费者清空。Python 在无活动任务时也会主动 invalidate 已存在的转发器，从未选中过任务的页面不因此创建快照。若当前与最后成功的消费者均已不可用，只能报告失败，不能保证清除其 DOM；等待消费者恢复后重试。无模型调用或全目录扫描。
- 250ms 是调度间隔，不是后台节流/页面冻结时的实时保证；恢复执行后会再次核对租期。getter 只供读取，已复制数据的其他消费者仍须处理失效。Python close 不立即清空已下发快照，页面租期负责停止更新后的清空。

## 验收

```sh
python -m unittest discover -s tests -q
node tools/verify_bridge.cjs
PYTHON=/path/to/python node tools/verify_cdp.cjs
PYTHON=/path/to/python node tools/verify_runtime_panel.cjs /path/to/frozen/legacy/scripts /path/to/evidence
PYTHON=/path/to/python node tools/verify_panel.cjs /path/to/frozen/legacy/scripts /path/to/evidence --bridge
```

Node 使用已有 Playwright，可通过 NODE_PATH 指向已有 node_modules。浏览器/日志/profile 都为本轮独立合成夹具，脚本清理自身临时目录并关闭自身子进程；截屏与固定消费者副本位于显式证据/临时目录，不属于安装或发行内容。

证据分层：

- Python 3.9.6 / 3.14.3 全套 92 项；包含配置边界与原读取/连接回归。
- Chromium / WebKit 页内契约：无选择不写、有效转发、任务变化清空、切回不复活、过期一次清空、消费者函数/getter 异常、时钟异常、初始化失败保留旧清空机制、停表后主动清空、活动与多选区别、多活动行/远程 host/云任务/非法 ID/缺失标记拒绝。
- 临时 Chromium 深浅主题端到端：真实 HTTP 发现 → WS → 宿主属性识别 → 显式合成日志 → 原面板。25% → 追加后 35% → 切换先清空 → 50%/900；缺失任务清空；Python 不再推送时面板主动过期清空；页面刷新后 hook 缺失明确报错，重新挂载后恢复且 HUD/伴宠各一个。无额外网络请求、无 pageerror。
- Chromium/WebKit × 深浅主题的现有面板兼容探针通过，桥直接在浏览器执行；WebKit 不是 CDP 运行时验证。两种引擎截图均已目检。
- 过期测试推进测试页 performance.now，并等待真实页内定时器清空 DOM；没有实等 120 秒。真实 CDP 额外核对含引号的载荷作为数据传递，不执行为脚本。
- 首次面板点击未先聚焦伴宠，详情位于视口外导致探针失败；按既有面板使用方式聚焦后重跑通过，没有为测试改面板样式或强制点击。最终审查的异常清理问题也先在浏览器复现失败，再补齐整体异常兜底、成功后交接定时器和 unselected 主动失效。

本轮证据目录 /tmp/quota-runtime-panel-evidence 与 /tmp/quota-runtime-webkit-evidence；临时文件可清理，长期留存可用上述命令重跑。

## 未完成边界与下一步

已打通隔离页面上的宿主标识 → 日志 → 现有面板更新链。真实 Codex 窗口没有注入或操作；没有完成原生 GUI、Windows 真机、生产目录自动关联、配额/历史/消息级数据、安装启动与发行验收。原 renderer 仍含待替换实现，不能据此宣称旧 injector 已全部替换。

下一步收口独立启动/运行入口与生命周期：保持显式授权目标、受限会话关联和用户退出语义，补齐连接状态诊断及消费者初始化/释放协议，再安排隔离原生验收。现用安装继续保持不变。
