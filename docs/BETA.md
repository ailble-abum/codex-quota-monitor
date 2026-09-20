# macOS V2 Beta：安装与换机开发

版本：`v2.0.0-beta.1`。这是需要手动配置的技术内测，不是双击即用的 macOS App，也不是 Codex 官方插件。

## 选择与更新

发布页：<https://github.com/ailble-abum/codex-quota-monitor/releases/tag/v2.0.0-beta.1>。

- `codex-quota-monitor-v2.0.0-beta.1-macos.zip`：独立目录运行包，包含已构建 renderer、来源声明和文件摘要，不依赖旧仓库。
- `codex-quota-monitor-v2.0.0-beta.1-devkit.zip`：本版本源码、测试、交接记录及内建伴宠资源；适合另一台 Mac 离线重建 renderer。Python 依赖和浏览器测试运行时仍需单独安装。
- `SHA256SUMS`：两个压缩包的校验值。将三个文件放在同一目录，运行 `shasum -a 256 -c SHA256SUMS`。

用户自行下载指定 Beta；不会强制更新、覆盖稳定版或更改稳定版 `main` 中的版本清单。本版没有内置稳定/Beta 频道开关、自动更新或一键降级；GitHub Pre-release 标记不等于这些功能已经实现。后续 Beta 同样手动下载到新目录，确认可用后再移除旧目录。

## 使用前提和边界

需要 macOS、Python 3.9 或以上及 `websockets==15.0.1`。本机已验证 Python 3.9 / 3.14；另一台 Mac、Intel Mac、不同 macOS/Codex 版本均需重新实测。没有 Windows、签名或公证验收。

内嵌面板需要宿主提供明确的本机回环调试端点。默认配置不会开启端口、启动或重启宿主；如在配置中增加明确的 `host_app` `.app` 绝对路径，监视器才会在端口不可用时请求退出并带本地调试参数重开该应用。这个 opt-in 路径尚未通过真实 Codex 整应用重启验收。

当前功能仍有缺口：普通启动自动跟随及整应用重启恢复未通过；健康、历史、通知等尚未全部接通。源码仍保留派生 renderer/资源及原 LICENSE/NOTICE，不宣称独立替换或法律审查完成。真实窗口刷新只有历史证据，本 Beta 包不据此宣称新一轮原生验收。

## 独立目录安装

1. 解压运行包到一个新的目录，保留原版程序和配置。先通过原版提供的方式停止原监视器，避免同一页面运行两个实例。不要同时启动原版与 Beta。
2. 在解压后的目录打开终端，创建本机自己的环境：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-cdp.txt
cp config.example.json config.json
```

3. 编辑 `config.json`：`origin` 填宿主已提供的本机回环端点，`page_url` 填已确认的完整页面 URL；`session_root` 填这台电脑上你授权读取的 Codex 会话目录绝对路径。真实 Codex rollout 目录另添加 `"session_layout": "codex-rollout"`。需要账户额度时添加 `"account_cli"`，其值为这台 Mac 的 Codex CLI 可执行文件绝对路径。没有配置账户 CLI 时，本地 token 与账户额度不可混为一谈。保留示例中的 consumer 相对路径和摘要，不复制另一台电脑的认证或会话文件。
4. 在该目录运行：

```sh
.venv/bin/python run.py --config "$PWD/config.json" --wait-for-host
```

本版是前台运行，不注册常驻服务。`discovery_unavailable` 表示端点不可用，`not_found` 表示没有匹配页面；状态不变时每 15 秒重试，不反复打印、不调用模型。`invalid_config` 请核对占位符、页面 URL、路径和 consumer 摘要；不要关闭摘要检查来绕过配置问题。

停止时按 Ctrl+C，并等进程退出。正常连接下退出会清理本实例的页面节点；断连时可能返回 `lease_pending`，不能当作清理已经确认。恢复连接并确认没有 Beta 面板残留后，按原版原有启动方式恢复原版。卸载只删除自己刚解压的 Beta 目录；不要删除认证、会话目录、原版安装或系统服务。切回原版的实际宿主操作仍需测试者在自己的电脑确认。

## 另一台 Mac 继续开发

首选克隆独立 Beta 分支，可保留全部 V2 提交历史并推送后续修改：

```sh
git clone --branch codex/v2-beta --single-branch https://github.com/ailble-abum/codex-quota-monitor.git codex-quota-monitor-v2
cd codex-quota-monitor-v2
```

先读 `AGENTS.md`、本文和 `docs/HANDOFF-2026-09-20.md`。开发工作基于 Beta 分支，不合并到稳定版 `main`。`devkit.zip` 内的源码是发布快照，不含 `.git`，但已包含仓库内伴宠资源；此目录及私人配置已列入忽略规则。

在源码目录或解压后的开发包目录中重建；输出目录必须事先不存在：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-cdp.txt
.venv/bin/python -m unittest discover -s tests
.venv/bin/python tools/build_panel.py candidate
.venv/bin/python tools/install_preview.py candidate preview
.venv/bin/python tools/audit_release.py preview
.venv/bin/python preview/run.py --help
```

构建器只使用仓库内 V2 模块和 `assets/companions`，生成的 manifest 标记为 `independent-v2-candidate`。生成的 preview 继续保留来源声明，默认只是技术预览。运行包的生成基于这个入口，不以拷贝本机现用安装、虚拟环境、用户配置或会话数据制作包。旧 `build_panel_candidate.py` 仅用于带归因的行为对照，不是发行入口。

`audit_release.py` 是发行前静态门槛：核对必需文件、consumer/安装清单摘要、独立构建状态，并拒绝旧 renderer 入口、认证/会话材料、日志和快照文件。它不能替代人工来源与权属审查。

浏览器验收另需 Node.js 和 Playwright 的 Chromium/WebKit。已有环境可设置 `NODE_PATH`；没有时在单独测试工具目录安装 Playwright 与对应浏览器，然后按交接文档运行。对运行包做 CLI 合成验收可设置 `QUOTA_RUNTIME_DIR=/absolute/unpacked/runtime`、`PYTHON=/absolute/python-with-websockets` 后运行 `node tools/verify_live.cjs`；这只连接临时 Chromium，不操作真实 Codex。

## 发布核查原则

两个压缩包均只从受版本控制的源码和已核对的仓库资源生成，附带 LICENSE/NOTICE。运行包文件摘要见 `install-manifest.json`；发行信息见 `BETA-RELEASE.json`。开发包同样记录发行信息。源码 Git 历史单独通过 Beta 分支保留。

实际验证证据见 `docs/BETA-VALIDATION.md`。合成浏览器与目录包检查不等同于另一台 Mac 的真实宿主安装、启动恢复和回退验收。
