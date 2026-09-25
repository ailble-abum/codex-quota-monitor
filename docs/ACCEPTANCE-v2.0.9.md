# v2.0.9 发行验收记录

日期：2026-09-25。使用合成页面与独立临时目录，不修改现用监视器、认证或会话记录。

- 六款伴宠的六格图集逐格目检，重点核对多手、轮廓与透明背景；Chromium/WebKit 均验证六款悬停换帧、图像解码与接触截图。
- Python 全套 210 项测试、伴宠运行时与行为检查、隔离候选的 Chromium/WebKit 面板挂载回归、Swift 类型检查和 arm64/x86_64 通用菜单程序编译通过。预览目录清单审计通过，68 个文件均在清单范围内。
- 正式 ZIP 解压后审计通过：69 个文件、68 个清单摘要；包内 consumer 的 Chromium/WebKit 挂载回归和 `run.py --help` 通过。ZIP 摘要为 `1af63dcd73e6fc5dd7598dc80de2ebaad6bee1d0145c71dfd90dd11a4db683b9`。
- 真实 macOS Codex 窗口、Windows 真机、签名和公证未在本轮验收。
- GitHub 正式发行页包含 ZIP、`SHA256SUMS`、`RELEASE.json` 三个文件。重新下载后三者与本地发行结果一致，`shasum -a 256 -c SHA256SUMS` 通过；未认证的 HTTPS 请求也可获取相同的 `SHA256SUMS`。标签 `v2.0.9` 指向来源提交 `982d9c7b2263a9bca08583f5e464b0dab6a89f2b`。
