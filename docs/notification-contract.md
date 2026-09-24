# V2 macOS 配额通知

2026-09-24。此功能仅在私有 `config.json` 显式设置 `"notification_root": "/absolute/private/path"` 后可用；面板开关仍默认关闭。用户在面板开启后，只根据已验证账户的实时额度触发通知。5 小时或每周窗口剩余不高于 20%、数据更新未超过 120 秒且重置时间在未来时，各账户、窗口和重置周期最多提醒一次。账户标识以 SHA-256 摘要处理；通知内容不含账户、会话或认证资料。

通知通过 macOS `osascript` 的 `display notification` 命令显示。通知状态写入指定目录的 `notifications.json`，文件权限为 `0600`；不配置该目录或用户关闭开关时不发送。退出或重启后的去重状态由该文件保存。通知失败不会阻断面板更新；系统通知权限和实际展示取决于运行该命令的 macOS 环境。

实现参考 [Apple 的通知脚本说明](https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/DisplayNotifications.html)。已通过合成发送器测试阈值、过期数据、跨账户和跨重置周期去重，以及 Chromium/WebKit 面板开关；尚未在真实 Codex 安装与系统通知中心验证。
