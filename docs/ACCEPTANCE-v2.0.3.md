# v2.0.3 发行验收记录

日期：2026-09-25。验收对象：`v2` 正式线，来源代码提交以本版 `RELEASE.json` 为准。所有测试使用合成页面、独立临时目录与唯一 LaunchAgent 标签；正在运行的 `CodexQuotaMonitorV2QA` 安装保持不变。

## 已验证

- Python 3.9 全套测试、Swift 类型检查、Chromium 与 WebKit 的面板挂载和更新提示测试均通过。发布 ZIP 的 `SHA256SUMS`、解压后文件清单与摘要、运行入口和面板资源另行核对。
- 用公开 GitHub 正式发行接口实际获取 v2.0.2 元数据、ZIP 和 `SHA256SUMS`，完成下载 SHA-256、包内逐文件摘要和安全解包验证。最初发现并修正错误 Accept 头和重复创建暂存目录。
- 在独立临时目录下创建合成 Codex 页面、旧版 v2.0.0 运行目录和唯一标签的 macOS LaunchAgent。旧版面板显示 `plugin 2.0.0` 后，运行修正后的安装器从公开发行包下载并切换；新版面板显示 `plugin 2.0.2`，页面中始终只有一个 V2 面板。这是对安装链的真机集成验收，未使用现用安装。
- 另以独立唯一标签的服务及菜单栏模拟进程执行真实 `launchctl bootout/bootstrap`：成功切换后两个进程均运行于新目录；注入菜单栏 bootstrap 失败后，旧 plist 和两个旧进程恢复运行。最终安装器在 bootout 后留出稳定时间，独立升级复测通过。
- 两组验收结束后测试标签已 bootout，临时目录已清理；现用 V2 服务和菜单栏仍指向原 `CodexQuotaMonitorV2QA/runtime` 且保持运行。

## 边界

面板点击与确认流程在 Chromium/WebKit 中使用合成载荷测试；真实 Codex UI 中的点击和用户本机现用安装未被修改。上述真机升级使用合成会话和独立 LaunchAgent 标签；菜单栏进程切换与正式包安装链分别验证。Windows 真机、签名与公证不在本版范围内。
