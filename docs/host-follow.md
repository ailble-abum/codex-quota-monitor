# 应用启动跟随：已实现部分与开放边界

2026-09-20。用户要求恢复旧版体验：普通打开 Codex 后面板自动出现；退出后不擅自重开应用；下次启动可恢复。不以手动运行调试命令作为最终交付。

## 旧行为与选型核查

只读核查相邻旧仓库的 start_codex_monitor.sh 与 reopen_codex_with_debug.sh：旧常驻启动器先等待用户打开应用，再检查调试端口；缺少端口时请求应用正常退出，等待退出后携带调试参数重开，并记录 PID 防止同一实例反复重开。因此旧版跟随体验还依赖应用重开这一环节，单独启动监视器不能取代它。

参考资料核查于 2026-09-20：

- [Electron 支持的命令行开关](https://www.electronjs.org/docs/latest/api/command-line-switches#--remote-debugging-portport)：remote-debugging-port 用于启用 HTTP 调试端口；文档也说明通过应用主进程添加开关须在 ready 前完成。这是文档支持，不是本项目可在任意已运行宿主中事后启用端口的证据。
- [Apple Launch Daemons and Agents](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)：复用系统 launchd 管理常驻进程；不增加进程管理库。KeepAlive 是保持任务运行的机制，不能作为一次性验收任务开关。

本轮复用 V2 现有 supervisor/UpdateLoop 和标准库 asyncio，仅补其等待策略，没有复制旧版启动器或实现退出/重开命令。

## 已实现：显式等待模式

`python -m quota_monitor.live --config /absolute/config.json --wait-for-host`

- 明确配置的回环端点不可用（discovery_unavailable），或该端点上没有指定页面（not_found）时，监视进程每 15 秒重试，保持同一个进程，不因达到默认失败上限而退出。
- 状态不变时不重复打印日志；恢复后使用原更新间隔继续读取与投影，不调用模型。
- 多个匹配页面、协议或消费者错误不作为正常等待，仍遵守 max-failures。
- --once 仍只检查一次并退出，即使同时传入等待选项。
- SIGINT/SIGTERM 仍取消等待并执行原有清理；没有启动、退出、重开宿主的能力。端点未开启时只能等待，不能解决普通图标启动缺少调试参数的问题。
- 选项默认关闭，原前台 CLI 的失败退出行为保持兼容；现用安装和 LaunchAgent 本轮未更新。

## 验证与限制

测试覆盖超过失败上限仍等待、端点恢复后更新、其他错误仍停止、状态日志去重、单次模式与取消。隔离 Chromium 验证关闭→重新创建浏览器两轮，同一监视 PID 自动重新挂载，每个页面只有一个消费者，合成 token 值恢复并能正常 SIGTERM 退出。该浏览器由测试夹具显式启动，不是监视器打开应用。

本轮验收：Python 3.9 与 Python 3.14 各运行 135 项测试，全部通过；`tools/verify_live.cjs` 的完整隔离 Chromium 验证通过；只读复核未发现确定性的逻辑、取消或回归问题。以上不代表真实应用普通启动验收。

后台重开 Codex 仍未实现、部署或验收。此前 Computer Use 对 com.openai.codex 给出明确安全拒绝；本轮不使用 CDP、AppleScript、后台任务或其他入口绕过。所有新运行测试均使用临时合成目标，不接触现用窗口。完整“点原图标自动跟随”仍未完成，未上传。
