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
