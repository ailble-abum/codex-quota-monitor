# 默认上下文与重启选择

2026-10-04：用户要求在插件中调整 Codex 的默认上下文，并在保存后选择是否立即重启；选择重启时自动拉起插件。这里的上下文指容量和自动压缩阈值，不是背景指令。

## 选型与来源

| 候选 | 核查与采用 |
| --- | --- |
| [官方配置参考](https://learn.chatgpt.com/docs/config-file/config-reference) | 文档确认 `model_context_window` 与 `model_auto_compact_token_limit`，未设置时沿用模型默认压缩阈值。采用这两个官方配置项。 |
| [官方 App Server](https://learn.chatgpt.com/docs/app-server) | 文档确认 `config/read` 和原子 `config/batchWrite`。本机 `codex-cli 0.159.0-alpha.12.1` 生成的协议 schema 和临时目录实测进一步确认版本检查、空值删除配置项、保留其他设置及注释。 |
| [官方开源模型配置实现](https://github.com/openai/codex/blob/main/codex-rs/models-manager/src/model_info.rs) | 源码核对：容量配置受模型 `max_context_window` 约束。插件不把任意输入当作模型真实能力，也不据配置伪造已观测上下文。 |
| 项目已有通信与启动模块 | 从现有账户读取中提取有界 App Server 通信层，额度与设置各用独立进程；复用 `HostFollower`、服务所有权检查和精确页面发现。没有引入另一套配置编辑器或新增生产依赖。 |

以上官方接口、已有实现已覆盖核心能力，故只增加差异化表单和明确选择的重启流程。依据协议与行为规格实现；未复制旧派生监控器或上述 Rust 源码，既有 LICENSE / NOTICE 保留。未发布新发行包。

## 行为

- 「设置 → 默认上下文」按需读取。本机全局默认值可被项目或配置档覆盖；ChatGPT 聊天禁用该入口。
- 两个输入均为正整数 Token 数；留空跟随模型。两者显式填写时压缩阈值必须小于容量。实际容量与压缩还受 Codex 模型限制约束。
- 保存和恢复默认仅编辑这两个配置项，使用官方原子写入与 `expectedVersion`。不改模型、认证、指令、会话或其他配置；旧版本冲突要求刷新，写入超时要求核对，不自动重复写入。
- 额度和上下文用量仍独立读取。打开设置、保存成功和选择「稍后」均不会关闭 Codex。
- 插件通过独立 App Server 保存配置，没有在桌面宿主中热更新运行线程。为确保新默认值生效，界面提示重启后用于新对话，不宣称当前对话已立即采用。
- 保存后显示「立即重启 / 稍后」。前者仅在本项目拥有采集服务的 macOS 安装中可用：先确认或恢复采集与自有菜单服务，再正常退出明确的 Codex 应用，重新打开时带上原监控配置的回环连接参数，等待精确页面可连接，采集器继续运行并重新注入面板。不会启动另一份监控实例。
- 退出失败不强杀宿主；连接超时或服务恢复失败显示失败，可选择重试或稍后。立即重启期间禁用重复操作，失败后的重试有独立次数，避免旧失败状态错误解锁按钮。

## 验证

- Python 全量 269 项通过；包含设置白名单、投影隐私、冲突、保存/重置、超时不重试、取消、额度隔离、明确重启授权、启动服务、连接等待与失败处理。
- 本机 Codex CLI 在临时 `CODEX_HOME` 实测读取、保存、过期版本冲突、并发配置变更、恢复默认、保留无关配置与注释。没有读取或改写真实认证与会话。
- Chromium / WebKit 合成 UI 通过输入检查、连续刷新保留草稿、语言切换、保存后重启选择、「稍后」无操作、立即重启去重、失败重试、ChatGPT 禁用与释放清理；合成截图目视核对且无横向裁切。
- Chromium 完整 UI → CDP → 监控运行循环 → 本机官方 Codex RPC → 临时配置的读/写/重置通过；确认修改默认值不产生虚构用量进度条。
- 既有双浏览器挂载、卸载与模板回归通过。重启动作使用替身应用与服务，未关闭真实 Codex；不把模拟启动成功认作原生重启验收。Windows 与发行验收未执行。

重现关键验证：

```sh
.venv/bin/python -m unittest discover -s tests
.venv/bin/python tools/verify_codex_context_defaults.py /path/to/codex
node tools/verify_context_defaults.cjs /path/to/consumer.js /path/to/evidence
PYTHON=/path/to/python node tools/verify_context_defaults_runtime.cjs /path/to/consumer.js /path/to/codex
```

本机安装结果另行补录；验收期间使用合成数据和独立临时目录。
