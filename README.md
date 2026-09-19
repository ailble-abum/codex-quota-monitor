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

[页面选择与更新循环](docs/runtime-contract.md) 已提供显式回环目标、增量日志更新与可过期的页面数值桥，通过临时 Chromium 恢复/切换测试。后续 [宿主活动任务与面板更新桥](docs/host-panel-contract.md) 已基于当前宿主资源核对属性，并在隔离 Chromium/WebKit 与外部面板中验证；真实原生窗口与安装接入仍未完成。

[独立前台运行入口](docs/live-contract.md)：`python -m quota_monitor.live --config /absolute/synthetic/config.json`，支持状态变化诊断、失败退避、信号退出与本实例页面释放。需显式目标；日志可选逐文件映射或[受限目录自动关联](docs/directory-index-contract.md)，暂无安装/自启动或真实原生验收。

[显式消费者初始化](docs/consumer-contract.md) 支持启动前脚本摘要校验、缺失时挂载和刷新恢复；外部 renderer 的来源替换与原生验收仍未完成。

[Renderer 首次拆分](docs/panel-split-contract.md) 提供带完整来源/许可的隔离候选，移除旧宿主扫描与观察器，保留现有面板视图；尚未完成整份 renderer 的来源替换。

[候选视图挂载替换](docs/panel-mount-contract.md) 已替换旧 ensureHud/ensureStyle，增加节点所有权保护和一次性事件绑定；HTML/CSS 视图资产继续归因。

[受管消费者卸载](docs/consumer-dispose-contract.md) 支持带 owner 保护的同步 dispose，候选可清理自有节点、全局拖动监听器及伴宠定时器；断连时仍报告未确认清理。

[保留样式范围清理](docs/panel-css-contract.md) 移除无调用样式，限制裸属性规则在面板内，避免修改宿主同名属性元素；其余保留样式继续归因。

[V2 数值显示替换](docs/panel-format-contract.md) 替换 token/pct 并移除旧 n，保留四种单位显示，拒绝非有限数值；完整 renderer 替换仍在推进。

[V2 控件状态和语言同步](docs/panel-controls-contract.md) 替换单位选中态和语言同步，补齐读屏选中状态，并修复自动单位文字无法随语言更新。

[V2 单位偏好](docs/unit-preference-contract.md) 初始化保留有效选择；单位写入失败时使用本次挂载的临时选择，恢复后可再次持久化。

[V2 会话详情正文投影](docs/panel-details-contract.md) 将详情卡片和说明改为文本 DOM，模型字符串不再解析为 HTML，空数据清空且重复更新保留原节点。

[V2 上下文正文投影](docs/panel-context-contract.md) 替换上下文数值和进度条构建，保留双语、边界值、无障碍及重复刷新行为。

[V2 本地健康提示正文](docs/panel-health-contract.md) 使用文本 DOM 和明确输入校验，统一建议与警告状态；真实健康数据生产链路仍待实现。

[V2 账户默认状态与底部文字](docs/panel-account-status-contract.md) 缺失账户数据不再显示读取中，底部状态改为纯文本；真实账户通路尚未接通。

[统一账户时效判断](docs/account-freshness-contract.md) 正文、标题和伴宠共用严格的 120 秒规则，拒绝缺失、未来及非数值时间。

[账户窗口整组校验](docs/account-windows-contract.md) 拒绝缺失、异常窗口及越界数值，统一降级账户显示并保持本地上下文更新。

[V2 账户窗口正文](docs/account-window-view-contract.md) 以文本 DOM 构建逐窗口内容，保留倒计时与预测；初始停靠组合的视口问题另列为待处理边界。

[固定停靠折叠往返修复](docs/docking-toggle-contract.md) 区分正常初始隐藏与固定状态丢失，修复折叠后重新展开时面板意外隐藏；左右停靠真实控件回归通过。

[V2 账户聚合正文](docs/account-overview-contract.md) 替换总预算、状态说明与附加用量，校验预算/用量/额度，过期数据不继续展示附加值。
