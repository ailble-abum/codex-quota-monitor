# Codex Quota Monitor v2.0.10 · macOS

修复伴宠多指触控时第二个指针可能接管拖动的问题。手势现在只接受启动它的指针；系统取消手势时恢复未保存的位置，不再触发落地反馈。伴宠触控区域声明 `touch-action: none`，让浏览器将拖动事件交给面板。

本版沿用 v2.0.9 的六款六表情素材。已安装 v2.0.3 或更新版本的用户可在面板点击“检测更新”；更早版本可下载 ZIP 与 `SHA256SUMS`，按包内 `RELEASE.txt` 手动安装。发行包未签名或公证。

发行包继续包含 Kevin Ke 与 Ailble 的 MIT `LICENSE` 和 `NOTICE`。[验收记录](ACCEPTANCE-v2.0.10.md)区分合成触控事件、真实 macOS UI 与 Windows 真机。
