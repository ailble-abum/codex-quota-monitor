# V2 本地健康提示正文

2026-09-20，接续 f27bc5f。移除固定外部 applyHud 的健康提示 HTML 拼接、标题和 warning 更新，改由 panel_health.js 的 renderHealth(body, health) 负责。任务关联仍由既有 companionHealth/快照链路决定；根缓存及伴宠反馈未改。

## 输入及显示

以标准 DOM 文本节点构建来源标签、次数、压后首请求、说明和交接建议，复用 token/pct 和视觉类名，无新增依赖。保留双语正文，并补齐英文 title。无健康对象或次数为零显示尚未观察到事件；次数必须是非负安全整数，无效次数显示数据暂不可用。字符串不解释为 HTML。

只有有效正次数且 recommendHandoff === true 才同时展示建议与 warning 样式。after 缺失为等待后续请求；非有限或负值为数据不可用。afterPercent 只接受 0–100 的有限数值，否则显示破折号。没有新推断或自动生成建议。

来源核对：旧仓库固定提交 2705f32a6f080ee1bdbecdc5b43f5fe0f9045eed 的 plugins/codex-quota-monitor/scripts/context_health.py:52–56 定义 reason 为 baseline/frequency/None。已知原因保留其经验阈值说明；未知原因明确依据未提供，不能默认解释为频繁压缩。整体 renderer 仍是带 LICENSE/NOTICE 的隔离派生候选，其余来源替换未完成。

更新比较当前节点与候选节点，内容不变时不替换子节点；warning/title 改变时单独同步属性。

## 验证

- verify_health.cjs 在实现文件缺失时先失败，完成后 Chromium/WebKit 通过有效与非法次数、等待请求、非法 after、严格布尔建议、已知/未知原因、双语及重复节点身份测试。
- verify_mount.cjs 完整候选通过合成健康记录、HTML 字符串次数拒绝和不同 healthThreadId 不展示；同时保留既有控件、单位、详情和节点所有权回归。
- 完整 Chromium/WebKit 明暗主题、数值、任务切换、缺失、过期和单实例验证通过；已目视核验 WebKit 无事件态的明暗主题截图。
- Python 3.9.6 / 3.14.3 全套各 120 项通过。

候选 /tmp/quota-health-candidate，截图 /tmp/quota-health-panel-evidence。仅为隔离合成浏览器证据；V2 当前实际日志投影尚无完整健康数据生产链路，不能把合成展示验收视为真实压缩检测完成。现用安装与真实会话未修改，原生窗口、Windows 和发行未验收。下一步继续梳理保留的账户/状态正文与标题更新边界。
