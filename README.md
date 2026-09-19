# Codex Quota Monitor V2

独立替换工作区，已实现日志增量读取、会话状态归约、任务身份核对、受限目录查找、旧面板数值投影与离线预览，尚无可安装版本。

目标：保留配额、会话统计、上下文、伴宠和本地历史能力，逐步替换旧版中的上游派生实现，并提高数据准确性、恢复能力与可维护性。

最新方向见 [最小替换范围审计](docs/source-audit.md)：保留本项目新增设计，只替换上游派生底层。此前的 [整体重建设计](docs/design.md) 已被该范围修订，不作为整体重写授权。旧版继续维护，V2 暂不连接或替换现用安装。

实现及证据见 [读取器契约](docs/reader-contract.md)、[会话归约器契约](docs/session-contract.md)、[数值兼容桥](docs/compat-contract.md)、[身份核对](docs/identity-contract.md) 和 [受限查找](docs/discovery-contract.md)。运行合成测试：

```sh
python3 -m pip install -r requirements-cdp.txt
python3 -m unittest discover -s tests -v
```

全套测试现在包含可选 CDP 通信层，推荐在虚拟环境中安装上述依赖。日志读取与离线预览本身仍不要求第三方包。[连接层契约](docs/cdp-contract.md) 记录了回环地址限制、超时/取消行为及临时 Chromium 验收。

新数据已通过 [隔离面板兼容验证](docs/panel-probe.md)：Chromium/WebKit 深浅主题、任务切换、缺失与过期清空。该验证使用外部现有面板，尚未独立替换其注入实现或接入现用安装。

[页面选择与更新循环](docs/runtime-contract.md) 已提供显式回环目标、增量日志更新与可过期的页面数值桥，通过临时 Chromium 恢复/切换测试。真实宿主任务识别与现有面板接入仍未完成。
