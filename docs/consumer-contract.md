# 显式消费者初始化

2026-09-20，接续 61b88fb。V2 初始化入口保留现有面板设计：调用方显式提供可信的本地 JavaScript 函数文件及 SHA-256，V2 在准确选定页面和有效活动任务上初始化缺失的消费者，然后复用现有数值桥。没有打包旧 renderer，也没有启动或操作现用安装。

## 配置与复用

```json
{
  "origin": "http://127.0.0.1:9222",
  "page_url": "http://panel.invalid/",
  "session_root": "synthetic-sessions",
  "panel": true,
  "consumer": {"path": "consumer.js", "sha256": "替换为可信文件的64位小写SHA256"}
}
```

示例中的 origin、页面及目录必须替换成调用方明确授权的隔离目标。consumer 可选，必须配合 panel=true。path 相对于配置文件目录；启动时读取一次普通文件，最大 512 KiB、严格 UTF-8、摘要必须匹配，之后内存固定至进程重启。配置/编码/摘要错误返回 invalid_config，不回显路径或脚本内容。仍受 CDP 1 MiB 请求预算限制；大量需要转义的源文件即使低于文件上限，也可能返回 request_too_large。

文件内容必须求值为同步函数 `empty => { ... }`（可加外层括号），函数必须注册 `window.__codexContextTokenInspectorUpdate`，接收首次空摘要。不接受 Promise 初始化。示例、隔离测试使用 DOM output 消费者；完整面板验证使用外部冻结来源，不将其代码或美术复制进 V2。

核查日期 2026-09-20：复用标准库 [hashlib.sha256](https://docs.python.org/3/library/hashlib.html#hashlib.sha256)、已有 CDP Runtime.evaluate 和 [JavaScript 函数表达式](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/function)，不增加注入框架或浏览器加密库。摘要在 Python 对原始字节计算，严格 UTF-8 解码后发送相同内容；不做换行转换。浏览器 WebCrypto 的异步/安全上下文要求在此没有收益，因此不采用。SHA-256 固定输入内容，不证明代码可信或来源合法。

## 生命周期

1. 每轮先通过既有目标选择和宿主适配获取活动任务；没有合法任务时不执行初始化。
2. 页内 prepare 再核对 URL 与任务。已有函数 hook 直接复用；非函数占位拒绝覆盖。prepare 缺失时才发送脚本，避免每轮传输大型美术资源。
3. initialize 同步再次核对 URL/任务及 hook，先写失败标记，再求值并以空摘要调用函数，成功后标记 ready。首次真实数值仍由 publish 再次核对任务后投影。
4. 初始化部分执行后失败、Promise 返回或 hook 随后丢失，均报告 javascript_error；失败标记阻止反复挂载，受现有连续失败限额约束。需要修复脚本并重新加载页面后恢复；不尝试回滚任意脚本副作用。
5. 页面刷新会清除标记和 hook，下一次有效任务更新自动初始化。已有 hook 不因摘要/文件变化被替换；更换消费者需要重新加载页面并重启 runner。
6. shutdown 仍只清空、停止并释放本实例的数据桥。消费者自己的 DOM、偏好、监听器可能保留；后续[受管卸载](consumer-dispose-contract.md)提供可选同步 dispose，未提供回调的消费者保持此行为。信号中断 CDP 收发时仍可能 lease_pending，不能算即时释放证明。

执行的是明确授权的本地代码，不是沙箱插件。摘要不限制消费者访问 DOM、网络或自身存储；本轮所有验收的网络都由临时浏览器路由隔离。现有渲染器仍含待审计/替换部分，不能称旧 injector 已独立替换，也不能因此删除原归因。

## 验证

- Python 单元与 CLI 子进程：固定字节、内容更改、大小/编码/摘要/配置拒绝，consumer 必须配合 panel=true，诊断脱敏。
- Chromium/WebKit：无任务/错页不执行、空摘要初始化、重复调用只挂一次、已有 hook 复用、丢失 hook 拒绝重装、抛错/部分注册/非函数/异步初始化拒绝且不重试。
- 真实 Chromium CLI：消费者文件由配置解析并初始化，日志数值、页面刷新恢复、单实例计数、SIGINT/SIGTERM、单次检查、目录失效清空与浏览器退出保持通过。
- 外部完整面板来源固定为旧仓库提交 `2705f32a6f080ee1bdbecdc5b43f5fe0f9045eed`，通过现有 AST 常量探针临时输出。真实 Chromium CDP 从无消费者页面初始化，追加/切换/缺失/过期/刷新恢复；Chromium/WebKit 深浅主题面板均由新初始化分支挂载。

本轮 Python 3.9.6 / 3.14.3 全套各 116 项通过；上述浏览器探针全部通过。已目视核对 WebKit 深浅主题截图，数值、文本与控件保持现有设计。截图位于 `/tmp/quota-consumer-webkit-evidence`，真实 CDP 面板证据位于 `/tmp/quota-consumer-panel-evidence`（本机临时证据，不作为发行资源）。

复现工具：`tools/verify_consumer.cjs`、`tools/verify_live.cjs`、`tools/verify_runtime_panel.cjs LEGACY_SCRIPTS ARTIFACT_DIR`、`tools/verify_panel.cjs LEGACY_SCRIPTS ARTIFACT_DIR --bridge`。仅临时 profile 和合成会话；没有真实原生窗口、Windows、安装或发行证据。

下一步为消费者来源拆分：按来源审计保留本项目面板设计，替换 renderer 中剩余继承的宿主/消息匹配与挂载逻辑，然后做隔离原生闭环。当前初始化入口解决启动顺序，不代替该源码工作。

后续进度：[Renderer 首次拆分](panel-split-contract.md)已实现仅接收有效 V2 快照的候选；保留视图继续携带原许可，剩余来源审计仍开放。
