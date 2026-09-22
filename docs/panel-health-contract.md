# V2 本地健康提示正文

2026-09-21，接续 f27bc5f。除正文投影外，新增仓库内 `HealthState` 从 V2 增量日志生成压缩健康快照；不读取或导入旧 `context_health.py`。

## 输入及显示

以标准 DOM 文本节点构建来源标签、次数、压后首请求、说明和交接建议，复用 token/pct 和视觉类名，无新增依赖。保留双语正文，并补齐英文 title。无健康对象或次数为零显示尚未观察到事件；次数必须是非负安全整数，无效次数显示数据暂不可用。字符串不解释为 HTML。

只有有效正次数且 recommendHandoff === true 才同时展示建议与 warning 样式。after 缺失为等待后续请求；非有限或负值为数据不可用。afterPercent 只接受 0–100 的有限数值，否则显示破折号。没有新推断或自动生成建议。

`HealthState` 只发布压缩次数、压后首请求、有限百分比、请求间隔和明确建议原因；未知原因不补造解释。伴宠通过 `healthThreadId` 只接收当前已核对任务的健康数据。整体 renderer 仍带 LICENSE/NOTICE；本地数值采样另见[采样摘要契约](panel-local-samples-contract.md)。

更新比较当前节点与候选节点，内容不变时不替换子节点；warning/title 改变时单独同步属性。

## 验证

- verify_health.cjs 在实现文件缺失时先失败，完成后 Chromium/WebKit 通过有效与非法次数、等待请求、非法 after、严格布尔建议、已知/未知原因、双语及重复节点身份测试。
- verify_mount.cjs 完整候选通过合成健康记录、HTML 字符串次数拒绝和不同 healthThreadId 不展示；同时保留既有控件、单位、详情和节点所有权回归。
- 完整 Chromium/WebKit 明暗主题、数值、任务切换、缺失、过期和单实例验证通过；已目视核验 WebKit 无事件态的明暗主题截图。
- Python 3.9.6 / 3.14.3 全套各 166 项通过（含 HealthState 的压缩/重复快照/重置测试）。

候选与真实 CDP r10 验证确认当前会话健康数据可以进入正文和伴宠；仍未完成原生窗口、Windows、通知、更新和正式发行验收。
