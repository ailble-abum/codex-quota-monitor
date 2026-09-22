# Codex Quota Monitor V2

macOS 技术内测：参见 [Beta 安装、回退与换机开发](docs/BETA.md)。Beta 由用户手动选择下载，不接入稳定版更新源；不是完整独立替换或普通启动自动跟随已完成的声明。源码分支 `codex/v2-beta`。

2026-09-20 接续状态：[官方插件内嵌与启动能力核查](docs/official-plugin-feasibility.md)。保留 Codex 内嵌额度条；尚未找到常驻侧栏的公开第三方插件接口，普通启动自动跟随及官方上架均未完成。下列各阶段记录应按对应日期和证据范围阅读。

独立替换工作区，已实现日志增量读取、会话状态归约、任务身份核对、受限目录查找、旧面板数值投影与离线预览，现有独立目录预览安装入口，尚非正式可替换版本。

目标：保留配额、会话统计、上下文、伴宠和本地历史能力，逐步替换旧版中的上游派生实现，并提高数据准确性、恢复能力与可维护性。

最新方向见 [最小替换范围审计](docs/source-audit.md)：保留本项目新增设计，只替换上游派生底层。此前的 [整体重建设计](docs/design.md) 已被该范围修订，不作为整体重写授权。旧版继续维护，V2 预览安装与现用安装隔离。

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

[V2 消息级用量恢复](docs/panel-host-details-contract.md) 由仓库内独立模块从增量日志投影受限的助手 Token chip 与活动侧栏提示，不重新引入旧 renderer 扫描层。

[V2 多任务侧栏摘要](docs/compat-contract.md) 在受限 rollout 目录模式下为已核对身份的任务提供数值摘要，详情与健康数据仍严格绑定当前活动任务。

[V2 上下文正文投影](docs/panel-context-contract.md) 替换上下文数值和进度条构建，保留双语、边界值、无障碍及重复刷新行为。

[V2 本地健康提示正文](docs/panel-health-contract.md) 使用文本 DOM 和明确输入校验，统一建议与警告状态；V2 `HealthState` 已从增量日志生成并在隔离 CDP 实例验证。

[V2 本地数值采样摘要](docs/panel-local-samples-contract.md) 通过显式 `history_root` 开关保存受限数值样本，面板只显示摘要，不保存原始会话内容。

[V2 账户默认状态与底部文字](docs/panel-account-status-contract.md) 缺失账户数据不再显示读取中，底部状态改为纯文本；真实账户通路尚未接通。

[统一账户时效判断](docs/account-freshness-contract.md) 正文、标题和伴宠共用严格的 120 秒规则，拒绝缺失、未来及非数值时间。

[账户窗口整组校验](docs/account-windows-contract.md) 拒绝缺失、异常窗口及越界数值，统一降级账户显示并保持本地上下文更新。

[V2 账户窗口正文](docs/account-window-view-contract.md) 以文本 DOM 构建逐窗口内容，保留倒计时与预测；初始停靠组合的视口问题另列为待处理边界。

[V2 账户速度估算](docs/panel-local-samples-contract.md) 从本地数值样本计算耗尽速度、均匀进度差和总预算；只有观察到实际下降才显示“按当前速度”，紧凑栏悬浮优先显示时间。

[固定停靠折叠往返修复](docs/docking-toggle-contract.md) 区分正常初始隐藏与固定状态丢失，修复折叠后重新展开时面板意外隐藏；左右停靠真实控件回归通过。

[V2 账户聚合正文](docs/account-overview-contract.md) 替换总预算、状态说明与附加用量，校验预算/用量/额度，过期数据不继续展示附加值。

[V2 版本、更新与界面诊断正文](docs/panel-diagnostics-contract.md) 改为文本 DOM；版本信息来自 V2 runtime，更新检查只有显式 HTTPS manifest 配置才联网。

[V2 正文挂载与语言重建](docs/panel-body-contract.md) 保留单位节点与设置区展开状态，修复切换语言后设置关闭但按钮仍标为展开的问题；正文模板继续归因。

[V2 语言偏好与事件](docs/panel-language-contract.md) 校验自动/中/英选择，读取失败回退自动，写入失败保留当前挂载的临时语言，正文重建不重复绑定。

[V2 复制交接动作](docs/panel-handoff-contract.md) 使用独立双语指令与根节点委托，阻止同按钮重复复制，并忽略已断开按钮的异步完成。

[V2 详情与皮肤展开偏好](docs/panel-disclosures-contract.md) 用根节点捕获事件替换旧绑定，初始化不写存储，语言重建保留当前展开状态，忽略旧节点事件。

[V2 伴宠动作与提醒偏好](docs/panel-companion-preferences-contract.md) 统一三个开关和五处行为读取，写入失败时保留当前挂载的临时选择，避免界面与行为不一致。

[配额通知可用性](docs/quota-notification-availability.md) 禁用尚未接通的通知开关，移除误导说明与无效偏好读写，保留原有存储值。

[V2 面板尺寸预设读取与事件](docs/panel-layout-preference-contract.md) 读取失败回退标准尺寸，统一按钮选中态和根节点委托，保留现有布局计算。

[V2 布局写入失败处理](docs/panel-layout-write-contract.md) 预设保存失败保留临时选择，布局保存异常不再中断界面更新；两个存储键仍独立保存。

[V2 位置重置](docs/panel-position-reset-contract.md) 删除记录失败也能复位当前界面，清理固定停靠状态和隐藏计时器，分别尝试两条记录清理。

[V2 伴宠尺寸偏好](docs/panel-scale-preference-contract.md) 统一手动/自动缩放与控件，保存或删除失败时保留当前挂载选择，恢复后可再次持久化。

[V2 边缘吸附偏好](docs/panel-edge-preference-contract.md) 关闭时立即解除停靠，写入失败保留当前选择；重新开启不会强制移动面板。

[V2 皮肤偏好与选择事件](docs/panel-skin-preference-contract.md) 仅接受注册皮肤，保存失败保留当前选择，伴宠、按钮和名称保持一致。

[折叠偏好存储容错](docs/panel-collapse-storage-contract.md) 读取失败默认展开，保存失败仍完成折叠布局更新。

[V2 持久布局输入校验](docs/panel-layout-data-contract.md) 拒绝非法结构和尺寸字段，保留有效坐标与左右停靠信息。

[V2 旧位置记录迁移](docs/panel-legacy-position-contract.md) 有效新布局优先，旧坐标逐项校验，仅迁移到当前内存。

[账户读取与预览安装](docs/account-and-preview.md)：可选官方 App Server 后台额度读取，独立目录安装与文件摘要清单；真实账户在隔离面板验证，原生及正式发行验收仍开放。

[本机 V2 切换](docs/local-switch.md)：支持按 Codex rollout 文件名定位当前任务，并继续核对内部身份；本机服务切换、原生验收和回退边界在此记录。

[原生恢复验收](docs/native-recovery.md)：真实窗口刷新已通过；整应用重启未通过，当前需手动恢复调试连接，详见记录。

[应用启动跟随](docs/host-follow.md)：新增可选安静等待与自动重连模式；完整普通启动跟随仍缺少端口开启环节，现用安装尚未更新。
