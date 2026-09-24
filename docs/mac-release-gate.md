# macOS 首个正式版验收门槛

2026-09-24。首个正式版限定 macOS；Windows 不在本轮发行范围。当前候选仍是隔离预览，不得仅凭目录审计或浏览器合成测试改标正式版。正式线 `main` 的未提交工作保持原样。

## 已完成的离线证据

- Python 3.9 全套 196 项、Swift typecheck、Chromium/WebKit 面板挂载和临时 Chromium 双次重启运行链通过。
- 最新独立包位于 `/Users/ailble/Desktop/季二六软件项目-V2验收包-20260924-r7`；`tools/audit_release.py` 验证文件清单与摘要通过。包内不含认证、会话或用户配置。
- 已用该目录生成确定性 `v2.0.0-rc.4` 候选 ZIP 和 `SHA256SUMS`；[候选包记录](candidate-package.md)保留校验值。`rc.1` 至 `rc.3` 已被替换；`rc.4` 仍明确标记为候选，不等于正式发布。
- V2 已有显式服务与菜单栏管理、官方账户读取、可选系统通知、七天采样与离线报告、更新检查，以及可检查真实发布状态的 `doctor`。

## 普通终端原生验收

仓库维护说明禁止本任务修改现用监视器安装、真实认证和会话文件。本会话用合成应用尝试 `launchctl bootstrap` 时返回 `bootstrap_failed`，已清理临时 plist；不要在同一受限会话重复尝试。以下步骤由有权操作该 Mac 的测试者在普通终端、独立预览目录执行：

2026-09-24 又用真实 Codex 对 `rc.2` 完成前台 `updated` 与 SIGINT `cleanup=released` 验证；V2 LaunchAgent 加载仍被本会话拒绝。旧版服务和菜单栏已恢复运行。剩余原生门槛仍需普通终端完成，不能把前台成功视为服务验收。

后续已修正默认用户域和虚拟环境解释器路径；`rc.4` 的 V2 服务与菜单栏 LaunchAgent 现均为 `running`，`doctor` 报告 `panel=updated`。V2 当前运行、旧版已停止；仍需确认菜单栏实际显示、Codex 退出重开、重新登录恢复和回退，才能发布正式版。

1. 确认稳定版监视器已通过其原有控制命令停止。不要在同一 Codex 页面同时运行两个监视器。
2. 在独立预览目录创建 Python 3.9+ 虚拟环境、安装 `requirements-cdp.txt`，复制 `config.example.json` 为私有 `config.json`。按本机实际环境填写 `origin`、`page_url`、授权的 `session_root`、`session_layout=codex-rollout`、`host_app` 和需要的 `account_cli`。保留 renderer 摘要；设置 `history_root` 与已有 `status_root`。不得把私有配置提交或加入发行包。
3. 先以前台模式运行 `run.py --config /absolute/config.json --wait-for-host`，打开并切换真实 Codex 任务，核对面板与菜单相关数据。停止后确认本实例的页面节点释放；断连时出现 `lease_pending` 不能算清理完成。
4. 用 `swiftc quota_monitor/QuotaMenu.swift -o QuotaMenu` 编译菜单栏程序，运行 `./QuotaMenu --report /absolute/history-root/history.json` 核对账户与报告；再用 `--run` 确认菜单栏显示、打开离线报告和退出动作。
5. 前台链通过后，执行 `python -m quota_monitor.service install --config /absolute/config.json`，检查 `status` 和 `doctor`。`doctor` 必须返回 `service=running`、`config=valid`、`panel=updated`；只看到进程运行不合格。若要测试菜单栏登录启动，再执行 `menu-install` 和 `menu-status`。
6. 依次测试 Codex 普通退出、重新打开、任务切换、页面重载和 Mac 重新登录后的恢复。V2 应等待用户再次打开 Codex，不应因退出而主动重开。检查通知只在用户打开开关且额度符合条件时触发。
7. 回退时先执行 `menu-uninstall`，再执行主服务 `uninstall`，确认两个标签均不在 `launchctl print` 中，且 V2 面板不残留。最后按稳定版原有方式恢复；不要删除认证或会话目录。

任一步失败时保存退出码、`doctor` 的安全状态字段和复现操作即可；不要共享认证、完整会话 JSONL 或私有配置。验收通过后再制作正式发行包、复核 LICENSE/NOTICE 与素材来源，创建正式 GitHub Release，并按发布范围更新 `main`。
