# v2.0.11 发行验收记录

日期：2026-09-26。发现现用 v2.0.9 LaunchAgent 反复以代码 2 退出，`doctor` 显示 `config=invalid`。配置的 renderer 文件及摘要一致，但文件约 1.44 MiB，超过 `load_consumer` 的 512 KiB 读取上限。排查仅读取状态，未修改现用安装、认证或会话记录。

- 新回归测试读取仓库实际构建的 renderer，并拒绝超过 8 MiB 的文件；Python 全套 211 项、Node 伴宠探针及 Swift 类型检查通过。
- 隔离预览清单审计通过，包含 68 个文件；正式包解压审计通过，包含 69 个文件。包内 `load_consumer` 成功读取 1,510,470 字节 renderer，Chromium/WebKit 挂载回归通过。
- 现用服务启动及真实 Codex UI：待另行验收。Windows 真机、签名与公证未验收。
- 发布后重新下载 ZIP 与 RELEASE.json 均与本地产物逐字节一致，SHA256SUMS 校验通过。ZIP 摘要为 `f40beda7449fa7e9742976953fee0fe63e43b957069ad0796192c536632ba380`，来源提交为 `d6efb11e1f9de15d2989a0f7d60407f06317cd69`。
