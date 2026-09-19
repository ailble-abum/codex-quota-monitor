# Codex Quota Monitor V2

独立替换工作区，已实现并验证日志增量读取基础模块，尚无可安装版本。

目标：保留配额、会话统计、上下文、伴宠和本地历史能力，逐步替换旧版中的上游派生实现，并提高数据准确性、恢复能力与可维护性。

最新方向见 [最小替换范围审计](docs/source-audit.md)：保留本项目新增设计，只替换上游派生底层。此前的 [整体重建设计](docs/design.md) 已被该范围修订，不作为整体重写授权。旧版继续维护，V2 暂不连接或替换现用安装。

首批实现及证据见 [读取器契约](docs/reader-contract.md)。运行合成测试：

```sh
python3 -m unittest discover -s tests -v
```
