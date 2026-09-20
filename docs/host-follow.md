# 应用启动跟随：已实现部分与开放边界

2026-09-20。用户要求恢复旧版体验：普通打开 Codex 后面板自动出现；退出后不擅自重开应用；下次启动可恢复。不以手动运行调试命令作为最终交付。

## 旧行为与选型核查

只读核查相邻旧仓库的 start_codex_monitor.sh 与 reopen_codex_with_debug.sh：旧常驻启动器先等待用户打开应用，再检查调试端口；缺少端口时请求应用正常退出，等待退出后携带调试参数重开，并记录 PID 防止同一实例反复重开。因此旧版跟随体验还依赖应用重开这一环节，单独启动监视器不能取代它。

参考资料核查于 2026-09-20：

- [Electron 支持的命令行开关](https://www.electronjs.org/docs/latest/api/command-line-switches#--remote-debugging-portport)：remote-debugging-port 用于启用 HTTP 调试端口；文档也说明通过应用主进程添加开关须在 ready 前完成。这是文档支持，不是本项目可在任意已运行宿主中事后启用端口的证据。
- [Apple Launch Daemons and Agents](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)：复用系统 launchd 管理常驻进程；不增加进程管理库。KeepAlive 是保持任务运行的机制，不能作为一次性验收任务开关。

本轮在 V2 supervisor/UpdateLoop 中增加了独立的 opt-in 跟随器，复用标准库 `subprocess`、`plistlib` 和 `asyncio.to_thread`，没有复制旧版启动器。只有配置 `host_app` 为明确存在的 `.app` 绝对路径时才启用；其他配置仍保持纯等待。

## 已实现：显式等待模式

`python -m quota_monitor.live --config /absolute/config.json --wait-for-host`

- 明确配置的回环端点不可用（discovery_unavailable），或该端点上没有指定页面（not_found）时，监视进程每 15 秒重试，保持同一个进程，不因达到默认失败上限而退出。
- 状态不变时不重复打印日志；恢复后使用原更新间隔继续读取与投影，不调用模型。
- 多个匹配页面、协议或消费者错误不作为正常等待，仍遵守 max-failures。
- --once 仍只检查一次并退出，即使同时传入等待选项。
- SIGINT/SIGTERM 仍取消等待并执行原有清理；未配置 `host_app` 时没有启动、退出、重开宿主的能力。端点未开启时只能等待，不能解决普通图标启动缺少调试参数的问题。
- 选项默认关闭，原前台 CLI 的失败退出行为保持兼容；现用安装和 LaunchAgent 本轮未更新。

## 已实现：显式宿主跟随

在配置中增加：

```json
"host_app": "/Applications/Codex.app"
```

当 `/json/list` 不可用时，跟随器只对这个 bundle 读取 `Info.plist`，必要时使用 `osascript` 请求该 bundle 退出，再用 `open -a ... --args` 带 `--remote-debugging-address`、`--remote-debugging-port` 和 `--remote-allow-origins` 重开。每次请求有 30 秒退避；命令失败不会打印路径、命令输出或认证信息，也不会扫描或终止其他应用。

这解决了“监视器一直等待但普通启动没有调试端口”的代码路径，但仍需真实 Codex 窗口验证：应用可能拒绝退出、忽略 Electron 参数或有活动响应。默认不启用，也不应在用户未确认的现用安装上直接打开。

## 验证与限制

测试覆盖超过失败上限仍等待、端点恢复后更新、其他错误仍停止、状态日志去重、单次模式与取消。隔离 Chromium 验证关闭→重新创建浏览器两轮，同一监视 PID 自动重新挂载，每个页面只有一个消费者，合成 token 值恢复并能正常 SIGTERM 退出。该浏览器由测试夹具显式启动，不是监视器打开应用。

本轮验收：Python 3.9 运行 152 项测试，全部通过；跟随器只用伪造 `pgrep`/`osascript`/`open` 命令验证；浏览器运行时不可用，未把 `verify_live.cjs` 记为通过。以上不代表真实应用普通启动验收。

后台重开 Codex 的实现已加入但仍未部署或真实验收。此前 Computer Use 对 com.openai.codex 明确返回安全拒绝；本轮跟随器只在合成命令测试中验证，不接触现用窗口。完整“点原图标自动跟随”仍待真实 macOS 安装、退出重开和下次启动恢复验收。
