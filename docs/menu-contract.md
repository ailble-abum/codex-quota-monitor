# V2 macOS 菜单栏候选

2026-09-24。`quota_monitor/QuotaMenu.swift` 是独立 AppKit 菜单栏程序，读取用户显式配置的 `history_root/history.json`。最近采样未超过 120 秒时显示当前账户已报告窗口的最低剩余百分比；否则显示 `—`。菜单显示同一账户近 7 天的采样次数和主要模型、项目。它不打开或读取认证文件、完整会话记录，也不启动或重启 Codex。

在隔离预览目录中可手动编译和启动；先配置并启动 V2 运行时，使其写入本地历史：

```sh
swiftc quota_monitor/QuotaMenu.swift -o QuotaMenu
./QuotaMenu --report /absolute/history-root/history.json
./QuotaMenu --run /absolute/history-root/history.json
```

`--report` 只打印合成报告，便于无 UI 验证；`--run` 创建系统菜单栏项目，菜单中的退出项只退出该程序。实现依据 [Apple NSStatusBar 文档](https://developer.apple.com/documentation/appkit/nsstatusbar/system)。已通过 Swift typecheck 和临时 JSON 的命令模式测试；尚未在真实 Codex 安装中验收菜单栏展示，也尚未把菜单程序加入 LaunchAgent 安装流程。
