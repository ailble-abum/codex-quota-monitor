# V2 macOS 常驻服务入口

2026-09-24。V2 安装目录现在包含 `quota_monitor.service`，可显式为当前用户注册独立标签 `local.codex-quota-monitor-v2`。它使用 Python 标准库生成 LaunchAgent plist，并调用 `/bin/launchctl bootstrap gui/<uid>`；`RunAtLoad` 与 `KeepAlive` 让 V2 进程在登录后保持运行。实现依据是 [Apple Launch Agents 文档](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)；已核对配置格式和合成命令结果，尚未在真实安装中验证。

在已解压的 V2 运行目录、使用已安装 `websockets==15.0.1` 的 Python 环境，填好私有 `config.json` 后执行：

```sh
.venv/bin/python -m quota_monitor.service install --config "$PWD/config.json"
.venv/bin/python -m quota_monitor.service status
.venv/bin/python -m quota_monitor.service doctor
.venv/bin/python -m quota_monitor.service uninstall
```

服务模式要求显式配置 `host=codex-sidebar`、`panel=true`、有效 `consumer` 摘要和 `host_app`。安装前检查 `.app`、本机回环端口与 renderer 摘要；缺少依赖、已存在同名 plist 或 `launchctl bootstrap` 失败时拒绝注册。只有本工具写入、且指向当前 V2 运行目录的 plist 才允许卸载；拒绝覆盖其他服务。`doctor` 仅核对服务是否运行及配置/renderer 是否仍有效，不等于面板已进入真实 Codex 窗口。运行时仍以 V2 `HostFollower` 等待用户打开应用；用户退出后不主动重开。

验证使用临时目录、合成 `.app` 和模拟 `launchctl`，没有注册真实 LaunchAgent，也没有修改现用监视器安装。真实 macOS 启动、退出、更新和回退必须另行验收后才能将此入口列为正式安装路径。
