# V2 原生刷新与重启恢复验收

2026-09-20，用户授权继续验证真实窗口刷新和应用重启。V2 服务为 local.codex-quota-monitor-v2，安装目录 preview-20260920-switch，renderer 摘要 5187c944696a533573d9879120ae01f75519de12a6c52d01ef95b833e45b4fb6。

## 真实窗口刷新：通过

对唯一 app://-/index.html 主页面实际执行 Page.reload，重新连接后 performance navigation.type 为 reload。原生检查确认：活动行唯一有效、面板根节点唯一、consumer ready、摘要匹配、hook 匹配、快照新鲜、真实账户 quota live、唯一 summary 的任务身份与活动行一致。刷新前任务身份只在验收进程内存中核对，不保存正文或任务 ID。

原来的停靠隐藏状态恢复，伴侣可见；悬停后面板正常露出，移开后恢复隐藏。面板裁切图保留在本机临时目录，不纳入仓库。没有发送消息、修改会话或重启应用来冒充页面刷新。

## 整应用重启：未通过，当前连接待恢复

临时探针设计为先核对 V2 基线，再正常退出并带回环调试参数重新打开应用。但实际结果文件停留在 started，未记录通过；后续检查发现当前应用没有调试参数，V2 服务持续 discovery_unavailable。临时 local.codex-quota-monitor-v2-restart-probe 已移除，未再自动退出应用。首次完整重启过程缺少可信证据，不记为通过。

无害计数复现实验证明，本机 launchctl submit 创建的任务包含 keepalive 属性，OnDemand=false；计数从第 1 秒的 1 增至第 12 秒的 2，runs 同样从 1 增至 2，且上次退出码为 0。因此本轮采用该命令充当一次性探针的方式有误，会重新执行并覆盖 result。计数测试 label 也已移除并确认不存在。后续若获工具允许，应使用明确 KeepAlive=false 的一次性定义，并增加原子执行锁；本轮未再绕过限制重试应用操作。

恢复阶段，Computer Use 对 com.openai.codex 明确返回安全策略拒绝；因此停止所有针对该应用的 UI/CDP/AppleScript/终端重启替代路径。仅继续清理本次临时任务与记录。当前需用户手动正常退出应用，再从终端使用下面命令恢复此前的调试启动方式：

```sh
open -a /Applications/ChatGPT.app --args --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222
```

V2 LaunchAgent 保持启用，等待恢复连接；尚未确认恢复成功。

此验证仅覆盖保留当前 --remote-debugging-address=127.0.0.1 / --remote-debugging-port=9222 参数的重启，不代表从普通 Dock 启动时可以自动打开调试端口，也不代表系统重启或 Windows 验收。

本轮只进行运行验收和文档记录，没有修改产品代码；不重复运行无关单元测试。未上传。
