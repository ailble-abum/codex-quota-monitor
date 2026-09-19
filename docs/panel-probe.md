# 隔离面板兼容验证

2026-09-20。完成的是新数据链与现有消费者的离线浏览器验证，不是将独立运行时安装进 Codex，也不代表旧 injector 已被替换。

## 实现与安全范围

- tools/panel_fixture.py 在自动清理的临时目录生成合成 JSONL，通过 V2 discover → SessionJournal → panel_payload 产生两个不同任务和一个缺失任务的载荷。
- 只从显式传入的旧版 scripts 目录静态读取 Python 字面量：面板脚本、伴宠反馈与图像常量。使用 ast.literal_eval，不 import/exec 旧模块，避免实例化账户、通知、更新和历史组件。
- 外部消费者基线：原仓库 2705f32a6f080ee1bdbecdc5b43f5fe0f9045eed。面板与伴宠代码没有复制进 V2；它们仍是外部旧版消费者，不能将本次复用测试算作来源替换。
- tools/verify_panel.cjs 使用现有环境的 Playwright，只启动隔离 Chromium/WebKit 上下文。网络请求仅允许内存返回的 panel.invalid 测试页，其他请求一律阻断且导致检查失败。不连接 CDP、真实应用、账户或真实会话。
- 每轮关闭上下文与浏览器，临时日志自动清理。截图保存到调用方明确指定的证据目录，不作为发行资源。

## 接入修正

panel_payload 新增 observedAt（Unix 秒），标记本次载荷组装时间，使现有面板的 120 秒过期保护生效。不是日志最后请求时间；当前调用方在读取完成后立即组装。未来缓存不得靠重新组装载荷来刷新旧读数的时间戳，需要保留实际读取时间。无读取/轮询调度器被新增。

当前消费者源码已使用“最近请求”标签，与 latest_turn_* 的实际含义一致；此前契约指出的“本轮”文案风险在本次检查的外部版本已消除，未由本轮修改原项目。

## 可重跑命令

先让 Node 可找到已有 Playwright 包，并确保其 Chromium/WebKit 浏览器已安装；这是可选开发验证依赖，不是 V2 运行时依赖。

```sh
python3 -m unittest discover -s tests -q
node tools/verify_panel.cjs /absolute/path/to/legacy/scripts /absolute/path/to/evidence
```

本机使用 NODE_PATH=/Users/ailble/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules；测试命令不要求修改系统配置。Python 可用 PYTHON 环境变量指定。

## 本轮证据

- Python 3.9.6、3.14.3 全套 72 项通过；包括静态提取不执行旧模块、拒绝动态表达式、元数据/发现流水线、时间戳。
- Chromium 和 WebKit × light/dark 四组通过：25%/700 → 切换前清空 → 50%/900；缺失任务清空；同一载荷超过 120 秒后清空；重复更新只有一个 HUD 和伴宠；无 pageerror 或外发请求。
- 过期检查通过移动测试页时钟并重放原载荷验证消费者逻辑，没有实等 120 秒，也不声称断连调度器已验收。
- WebKit 深浅主题截图已目检，文本、数字、进度条和现有伴宠可见；测试页 UTF-8 编码问题已修复后重跑。
- 证据目录：/tmp/quota-panel-evidence.Kaye7p（临时证据可清理，需长期保存时重跑到指定目录）。

账户配额不在本次数据范围，页面的账户“正在读取/未更新”状态不能当作账户接口成功。消息级 Token、完整健康/历史接入、生产目录规模、原生 Codex UI、Windows 和发行仍未验收。

下一步替换独立连接层与更新循环，并在合成页面验证断连/重连和任务选择；保留现有产品设计。CDP/启动器/注入胶水等派生代码仍待处理，旧归因不变。
