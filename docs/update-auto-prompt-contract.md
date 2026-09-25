# V2 自动更新提示

2026-09-25。复用已有的后台 `UpdateSource`、GitHub 正式版查询和面板更新卡片，不增加请求、通知依赖或第二套弹窗。后台返回 `update_available` 且版本号有效时，面板自动展开设置区并将现有更新提示滚动到可视区域；安装仍由用户点击“安装并重启”触发。没有可用版本、检查中或查询失败时不自动弹出。

同一版本在当前面板中只自动弹一次。用户点击“关闭”后，将该版本号存入浏览器本地偏好；页面重建后不重复自动提示，手动点击“检测更新”仍可查看。新版本号会再次提示。存储不可用时使用当前面板的内存状态防止重复弹出，不因此阻止更新检查。

选型核查：2026-09-25 核对 [GitHub latest release 接口](https://docs.github.com/en/rest/releases/releases#get-the-latest-release) 的正式版语义，以及 [标准 DOM 滚动接口](https://developer.mozilla.org/en-US/docs/Web/API/Element/scrollIntoView)。项目已有这两条能力链，故直接接入现有投影与卡片；没有引入第三方更新提示库。文档语义和源码已核对，合成浏览器场景已验证；真实 Codex 原生窗口中的自动出现仍待单独验收。

合成 Chromium/WebKit 验证后台可用版本、收起面板、隐藏设置、提示可见、关闭后不重复、跨状态重绘和新版本再次提示；手动检查与安装按钮回归通过。截图位于 `/tmp/quota-auto-update-evidence`。测试不调用真实账户、会话或现用监视器。
