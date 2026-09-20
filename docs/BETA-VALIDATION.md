# v2.0.0-beta.1 验证记录

2026-09-20。本轮发布准备只增加 Beta 使用/换机说明、源码根目录来源声明、配置/构建忽略规则，并给既有 CLI 合成验收加入 `QUOTA_RUNTIME_DIR`，以便直接测试安装目录中的 Python 模块。没有修改产品运行逻辑或 UI。

## 本轮实际执行

- Python 3.9 / 3.14：`python -m unittest discover -s tests`，各 136 项通过。
- 从固定提交 `2705f32a6f080ee1bdbecdc5b43f5fe0f9045eed` 的六份输入重建候选，全部来源 SHA256 校验通过；由 `install_preview.py` 生成独立运行目录。
- renderer SHA256：`49ee1c7a6f4a4fd54259590c5613ffbdf7b2bd0dd24bf0c93ed95c02cbe3ee03`。
- 运行目录全部文件与安装清单 SHA256 一致；复制到仓库外临时目录后 `run.py --help` 成功且包含等待选项，随后删除该独立临时副本成功。这不是原生宿主卸载验收。
- 对生成目录设置 `QUOTA_RUNTIME_DIR` 运行 `verify_live.cjs`：临时 Chromium 中数值、刷新、SIGINT/SIGTERM 退出、单次运行、目录关联、歧义失效及宿主退出通过。等待模式经过两轮临时浏览器重建，监视进程 PID 保持不变，单消费者与退出通过。
- 对目录包内 renderer 运行 `verify_mount.cjs`：Chromium/WebKit 挂载、键盘及控件、外部节点保护通过。
- `verify_panel.cjs --bridge`：Chromium/WebKit × 明暗主题，数值、任务切换、缺失、过期及单实例通过；WebKit 明暗截图已目视核对。截图含合成任务，不含真实会话或账户响应。边缘伴宠在该停靠视口存在裁切，完整布局适配仍属于后续工作。

## 证据边界

这些是本机单元、目录包和合成浏览器证据。没有操作真实 Codex、替换本机现用安装、上传认证/会话记录，未执行新的真实账户读取。并非另一台 Mac、Intel Mac、真实宿主安装/回退、普通图标启动、整应用重启、签名/公证或 Windows 验收。

目录安装器覆盖拒绝覆盖已有目录、摘要篡改拒绝、畸形清单受控失败；合成浏览器覆盖正常退出清理。真实宿主断连时仍可能为 `lease_pending`，不宣称原生卸载/回退已验收。

纯文档与归因文件不适用新增功能单测；CLI 验收入口的单行调整通过实际目录包运行验证。压缩包的构建提交与摘要以发行附带的 `BETA-RELEASE.json`、`install-manifest.json` 和 `SHA256SUMS` 为准。
