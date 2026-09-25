# v2.0.11 发行验收记录

日期：2026-09-26。发现现用 v2.0.9 LaunchAgent 反复以代码 2 退出，`doctor` 显示 `config=invalid`。配置的 renderer 文件及摘要一致，但文件约 1.44 MiB，超过 `load_consumer` 的 512 KiB 读取上限。排查仅读取状态，未修改现用安装、认证或会话记录。

- 新回归测试读取仓库实际构建的 renderer，并拒绝超过 8 MiB 的文件；Python 全套 211 项、Node 伴宠探针及 Swift 类型检查通过。
- 隔离预览清单审计通过，包含 68 个文件；正式发行包及包内 consumer Chromium/WebKit 回归、ZIP 摘要：待完成。
- 现用服务启动及真实 Codex UI：待另行验收。Windows 真机、签名与公证未验收。
- 发布后重新下载校验：待完成。
