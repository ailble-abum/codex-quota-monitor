# v2.0.0-beta.1 验证记录

2026-09-20。本轮继续完成 V2 renderer 的独立 shell、伴宠资源内建和目录安装入口；没有修改真实认证、会话或现用监视器安装。

## 本轮实际执行

- Python 3.9：`python -m unittest discover -s tests`，152 项通过。
- `.venv/bin/python tools/build_panel.py candidate`：不读取旧仓库脚本，直接拼装仓库 V2 模块并编码 `assets/companions`；生成清单状态为 `independent-v2-candidate`，最终 `consumer.js` 通过 Node 语法检查。
- 12 个 WebP 资源与历史归档 data URI 逐字节一致；候选携带根目录 `LICENSE`/`NOTICE`。
- `tools/install_preview.py` 接受新候选并在仓库外临时目录生成独立运行目录；`run.py --help` 和目录摘要检查通过。目标目录已存在、摘要篡改和畸形清单仍受控失败。
- `tools/audit_release.py` 对临时目录包通过：必需文件、consumer/安装清单摘要和独立构建状态一致；人工来源/权属审查仍未完成。
- 已用仓库记录的 `NODE_PATH` 定位 Playwright；但其期望的 Chromium headless shell 与本机缓存版本不匹配，WebKit 可执行文件也缺失，因此本轮不计 `verify_mount.cjs`、`verify_panel.cjs` 或 `verify_runtime_panel.cjs` 的浏览器通过。

## 证据边界

这些是本机单元、目录包和静态构建证据。没有操作真实 Codex、替换本机现用安装、上传认证/会话记录，未执行新的真实账户读取。并非另一台 Mac、Intel Mac、真实宿主安装/回退、普通图标启动、整应用重启、签名/公证或 Windows 验收。

目录安装器覆盖拒绝覆盖已有目录、摘要篡改拒绝、畸形清单受控失败；合成浏览器覆盖正常退出清理。真实宿主断连时仍可能为 `lease_pending`，不宣称原生卸载/回退已验收。

纯文档与归因文件不适用新增功能单测；独立构建与安装入口均有对应测试。正式压缩包的构建提交与摘要仍需在浏览器运行时可用、来源审查完成后，以发行附带的 `BETA-RELEASE.json`、`install-manifest.json` 和 `SHA256SUMS` 为准。

## 2026-09-23 后续验证

- Python 3.9 全套 177 项通过；`tools/verify_live.cjs` 通过临时 Chromium 的相对配置、重载恢复、SIGINT/SIGTERM 清理、目录索引歧义、页面关闭和等待模式重开。
- `tools/verify_runtime_panel.cjs` 使用 V2 独立候选在 Chromium 明暗主题通过真实 CDP、追加、任务切换、缺失、自动过期、重载和单实例；`tools/verify_panel.cjs --bridge` 在 Chromium/WebKit 明暗主题通过。侧栏只保留 V2 自有摘要属性，宿主文字与状态不变。
- 预览目录 `beta-20260923-r20` 的独立构建、12 个视觉资源哈希、安装清单和 `audit_release.py` 均通过。该目录仍是隔离预览，不替换稳定版安装。
- 以上补齐了合成浏览器证据，不等同于真实 Codex 整应用退出重开、LaunchAgent 切换、Windows、签名/公证或最终来源/权属审查。

## 2026-09-24 发行门槛复核

- Python 3.9 全套 182 项通过；新增发行审计测试拒绝清单外文件、发行目录外路径、renderer 路径逃逸和包内符号链接。`audit_release.py` 要求安装清单恰好覆盖预览目录内除清单自身外的全部普通文件。
- 使用新临时目录执行 `build_panel.py` → `install_preview.py` → `audit_release.py`，62 个文件中 61 个均有摘要，状态为 `audited`；`run.py --help` 通过。consumer 摘要为 `f07d910fdf7d11aa57baabf0358ad3a910b181596759f5de2df02b6d830d5444`。
- 新构建候选在 Chromium/WebKit 通过挂载隔离及控件、键盘、单位切换、拖动点击抑制和外部节点替换保护测试；临时 Chromium CLI 通过双次浏览器重启恢复、同 PID 等待、单消费者、会话目录歧义、信号清理和无宿主数据测试。
- 以上仍是合成测试和隔离预览。未修改稳定安装或 LaunchAgent；真实 Codex 整应用退出重开、Windows、签名/公证以及素材来源/权属审查均未验收。

## 2026-09-24 通知接线复核

- Python 3.9 全套 182 项通过，包括通知阈值、过期数据、发送失败、跨账户与重置周期去重，以及私有通知目录配置。
- Chromium/WebKit 的 `verify_mount.cjs` 通过通知开关启用、关闭、持久化与未配置时禁用；临时 Chromium 的 `verify_live.cjs` 通过双次浏览器重启恢复与信号清理。
- 新临时目录执行 `build_panel.py`、`install_preview.py`、`audit_release.py`，64 个文件中 63 个均有摘要，状态为 `audited`；consumer 摘要为 `2059870aef48a83bfb32f190c612f324f4421048fe6c0108cb5f88ec68e81677`。
- 未向真实通知中心发送消息，也未改动真实 Codex 或现用监视器。正式版门槛仍有真实原生安装/恢复、素材来源审查、Windows 范围确认及签名/公证决策。

## 2026-09-24 七日报告复核

- Python 3.9 全套 185 项通过；包括已验证任务的项目标签提取、身份冲突清空、账户隔离、7 个 UTC 日汇总和项目/模型采样次数。
- Chromium/WebKit 面板挂载测试通过报告文本节点显示和 HTML 注入抑制。独立临时目录包经构建、安装和静态审计通过：64 个文件中 63 个有摘要，consumer 为 `3f259eb39bdaad462207bf38b3bd75097dbe7bad6210fa5c1fa753bdc47f93dc`。
- 这仍是采样报告，不代表逐请求、逐 token 的完整用量周报；真实 Codex 原生展示尚未验收。

## 2026-09-24 菜单栏候选复核

- `swiftc -typecheck quota_monitor/QuotaMenu.swift` 通过；在临时目录编译出的命令模式用合成历史 JSON 验证最新账户选择、余额显示、七天采样和路径不出现在输出中。
- 未注册 LaunchAgent、未读取真实历史文件；原生菜单可见性和服务集成仍需验收。
- 后续用独立临时目录中的合成 `history.json` 启动 `--run`，进程保持运行 2 秒且无 stderr，然后发送 SIGTERM 退出。此项只确认 AppKit 程序可启动，不包含真实菜单可见性或 Codex 集成验证。
- 隔离服务测试用临时 plist、合成配置与模拟 `launchctl` 验证菜单栏注册、状态、卸载及主服务卸载顺序；未注册真实 LaunchAgent。

## 2026-09-24 本机 launchd 加载尝试

- 确认当前用户域没有 `local.codex-quota-monitor-v2` 后，用独立临时目录、合成 `.app` 和空会话目录执行一次真实 `Service.install`；`launchctl bootstrap` 返回 `bootstrap_failed`。安装器移除了刚创建的 plist，后续只读 `launchctl print` 确认该标签不存在。
- 按仓库维护说明，本会话不重复尝试注册。需要在用户的普通终端对隔离预览包执行服务加载/`doctor`，并分别核对菜单栏、真实 Codex 面板与退出恢复；此处不能把模拟命令通过当作原生验收。

## 2026-09-24 伴宠状态回退

- 其余五款没有独立表情帧的伴宠现在也会应用 `idle`、`concerned`、`waiting`、`happy`、`notice`、`pet` 状态，使用现有单帧素材的 CSS 明暗/饱和度/轻微位移；`prefers-reduced-motion` 禁用位移过渡。猫仍使用原有六帧。
- Python 3.9 全套 187 项与 Chromium/WebKit 挂载测试通过；这不是新增表情插画或实际原生视觉验收。

## 2026-09-24 正式线功能迁入复核

- 只读检查正式线已提交源码和当前未提交改动，没有修改正式线工作区。V2 适配了手动检查更新按钮及强制刷新入口，并依据正式线离线周报的功能需求，使用 V2 自有采样格式生成当前账户的 `history.html`；菜单栏新增打开该文件的入口。
- Python 3.9 全套 189 项、Swift typecheck、Chromium/WebKit 面板挂载测试和临时 Chromium 双次浏览器重启运行链通过。离线页测试验证跨账户隔离、HTML 文本转义和 `0600` 文件权限。
- 新的独立预览包 `/Users/ailble/Desktop/季二六软件项目-V2验收包-20260924-r2` 通过静态审计：66 个文件中 65 个有摘要，consumer 为 `eb907dd5acd5848ebd4fdf0d123984eb3f779d48bcf26d94f0a89dd5eff94e86`。它不含私有配置，也没有启动真实 Codex 或安装 LaunchAgent。

## 2026-09-24 面板状态诊断复核

- 在 V2 新增显式 `status_root`，以 `0600` 私有 JSON 记录短状态码与时间戳；`doctor` 在服务运行且配置有效时核对该标记的新鲜度，只有最近 `updated` 可报告面板发布成功。
- 使用临时目录和模拟 `launchctl` 测试状态缺失、有效、过期与服务诊断；监督循环测试确认发布与停止状态被写入。真实 Codex 与 LaunchAgent 联合验收仍未完成。
- Python 3.9 全套 192 项、Swift typecheck 与临时 Chromium 运行链通过。首次目录审计发现源码文件名含发行禁用词 `snapshot`，已改为 `runtime_marker.py` 后重建；最新隔离预览目录 `/Users/ailble/Desktop/季二六软件项目-V2验收包-20260924-r4` 经审计通过，67 个文件中 66 个有摘要。
