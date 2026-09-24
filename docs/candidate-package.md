# V2 macOS 发行候选包

`tools/package_candidate.py` 只接受已通过 `audit_release.py` 的隔离预览目录，向一个尚不存在的输出目录生成确定性 ZIP、`SHA256SUMS` 与 `CANDIDATE.json`。它拒绝覆盖现有输出，ZIP 内保留随 renderer 分发的 MIT `LICENSE`/`NOTICE`，清单明确标记 `candidate-not-release`。包中只有源码、renderer 和配置示例，不复制虚拟环境、认证、会话或运行状态。

当前候选位于 `/Users/ailble/Desktop/季二六软件项目-V2发行候选-20260924-rc2`，文件名 `codex-quota-monitor-v2.0.0-rc.2-macos.zip`，SHA-256 为 `04a3804d99f70342bc80fddfed938110531ce2288872bea80c45c2d46193f291`；`shasum -a 256 -c SHA256SUMS` 已通过。此前的 `rc.1` 缺少严格的 `doctor` 退出码判断，已被 `rc.2` 替换，不再用于原生验收。`rc.2` 仍只是候选标签，包内运行版本与 GitHub 正式发布标签尚未提升。

`rc.2` 归档已在独立临时目录解压复核：包内文件审计、CLI 帮助命令、Swift 类型检查及合成 Chromium 运行链均通过。`rc.1` 另通过 Chromium/WebKit 面板挂载；两者 renderer 摘要相同。测试只使用合成数据；原生服务、菜单栏可见性和真实 Codex 面板仍按发行门槛单独验收。

该工具为正式发行准备可重复的输入，但不会创建 tag、推送 release、修改 `main` 或注册系统服务。只有 [macOS 原生验收门槛](mac-release-gate.md) 通过后，才可决定最终版本号、重建发行内容并发布。
