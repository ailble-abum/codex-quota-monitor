# Codex Quota Monitor v2.0.5 · macOS

菜单栏增加 Token 活动：显示官方账户接口提供的最近日用量和累计活动。字段缺失时显示 `—`；采样超过 120 秒后不显示旧数值。数据仍按当前账户隔离，只保存两个经过数值校验的指标，不保存原始活动响应。

已安装 v2.0.3 或 v2.0.4 的用户可在面板点击“检测更新”，选择“安装并重启”。更早版本需手动下载 ZIP 与 `SHA256SUMS`，校验后按包内 `RELEASE.txt` 操作。旧目录和 Python 虚拟环境应保留以便回退。发行包未签名或公证。

发行包继续包含 Kevin Ke 与 Ailble 的 MIT `LICENSE` 和 `NOTICE`。原生菜单栏 UI、Windows 真机、签名和公证的验证边界见[验收记录](ACCEPTANCE-v2.0.5.md)。
