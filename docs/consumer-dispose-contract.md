# 受管消费者卸载

2026-09-20，接续 3b5dd76。初始化函数可以返回 `{dispose() { ... }}`，提供同步卸载回调。没有该回调的已有消费者继续遵守“清空并释放数据桥”的原契约，不能据 released 推断其 DOM 已删除。

## 所有权与错误

- initialize 记录调用实例 owner、实际注册的 hook 及可选 dispose。只有成功发布并使用同一个 hook 时，消费者卸载权才随数据桥转交给最新 owner。旧实例的 release 不清除新实例状态。
- release 必须匹配数据桥 owner（若存在）、消费者 owner 及当前 hook 身份。hook 被其他函数替换时不调用旧卸载回调；不猜测新消费者属于谁。
- 尚未发布过数据、但已经初始化成功的 runner 也会在 shutdown 请求释放。初始化收发中被取消时记录存在未确认资源，报告 lease_pending。
- 回调必须同步完成；抛错、返回 false 或 Promise 均为失败。卸载前置失败标记，失败消费者不可再被 prepare 当作 ready。成功后删除仍属于该实例的 hook 和消费者标记；数据桥仍按原逻辑停止定时器并释放快照。
- released 表示确认完成本次可用协议：有受管回调时包含其成功返回，无回调时只代表数据桥释放。连接已断开或收发被信号打断时仍可 lease_pending；120 秒数据租期不是 DOM/监听器卸载保证，不能宣称无残留。

这只是单页面单活跃更新者的退出保护，不新增多进程调度或自动接管协议。未成功返回回调的初始化半成品仍不能通用回滚，需重新加载隔离页面。

## 候选实现

候选新增 disposePanel，保存自己的 panel/style/mascot 对象引用。删除通过对象引用执行，不通过同名 ID 删除替换节点。伴宠构造和提示定位加生命周期检查；旧 hook 保存后再调用会拒绝渲染。候选不再写旧 runtime version 全局标记。

复用已核对的 retained view 清理接口：panel.__ctiRemoveResize 清理 pointermove、pointerup、pointercancel、resize；panel.__ctiClearHint 清理提示节点与 timer。另清理停靠隐藏、抚摸和伴宠反应三个 timer。DOM 移除后不再可由用户交互触发其元素监听；本轮没有对任意第三方脚本持有并主动触发已脱离文档的元素引用作保证。

微任务/图片 load 后续提示定位由 disposed 检查阻断；卸载后的受管 update 拒绝重新挂载。localStorage 中的单位/布局等偏好保留，不清理宿主或用户数据。原 stylesheet、HTML、伴宠与保留辅助函数仍带原许可，整体 renderer 来源审计继续开放。

## 验证

新增 tools/verify_dispose.cjs（输入生成候选）在 Chromium/WebKit 验证：

- 初始化后、尚未发布即 release，三个主节点删除，四项全局监听清除。
- 保存的旧 update 调用失败；同页重新初始化后可正常更新。
- A 发布、B 接管后 A 的 release 不卸载；B 退出可卸载。
- 三个计时器均有实际 ID 且观察到 clearTimeout 调用；等待后不重新出现面板或提示。
- 同名伴宠被外部节点替换后，只移除旧所属节点、保留外部内容。
- 重复 release 幂等。

verify_consumer.cjs 另覆盖回调抛错/false/Promise、失败后 prepare 拒绝、hook 替换不调用旧 disposer。Python 测试覆盖初始化尚未发布时 shutdown、断连无法确认清理。真实 Chromium CDP 面板 worker 改用 shutdown，停止后断言面板/样式/伴宠及 update hook 都已移除。真实 CLI 探针使用同步 disposer，验证 SIGINT/SIGTERM 后回调执行一次且消费者标记删除；无 disposer 的早期 CLI 回归及 Chromium/WebKit 数据桥回归也通过，保留兼容性。

合成 pointer 定时器测试中 setPointerCapture 使用 no-op，仅验证资源清理；不冒充原生指针捕获或真实拖动验收。完整面板仍沿用深浅主题/刷新/切换/过期验证。没有修改真实会话、认证或现用安装，没有原生窗口/Windows/发行证明。

Python 3.9.6 / 3.14.3 全套各 119 项通过；已目视核对 WebKit 深浅主题截图，显示保持一致。输出摘要及原 LICENSE/NOTICE 一致性核验通过，临时冻结源码已清理。

生成候选 `/tmp/quota-dispose-candidate-final` 和截图 `/tmp/quota-dispose-runtime-evidence` 是本机隔离证据。下一步继续共享样式和保留格式化/展示函数的来源替换；账户、历史、完整伴宠交互与隔离原生验收仍待完成。
