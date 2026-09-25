# Codex Quota Monitor v2.0.11 · macOS

修复 v2.0.9 起六款表情使 renderer 超过 512 KiB 后，主监视器启动时拒绝读取自身文件的问题。读取上限现与隔离预览和发行包统一为 8 MiB，仍要求普通文件及 SHA-256 摘要匹配。

已安装 v2.0.9 或 v2.0.10 且主监视器无法启动时，请下载本版 ZIP 与 `SHA256SUMS`，校验后按包内 `RELEASE.txt` 在新目录安装。旧目录及私有配置保留以便回退。发行包未签名或公证。

发行包继续包含 Kevin Ke 与 Ailble 的 MIT `LICENSE` 和 `NOTICE`。测试范围见[验收记录](ACCEPTANCE-v2.0.11.md)。
