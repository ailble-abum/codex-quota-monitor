# V2 持久布局输入校验

2026-09-20，接续 07605a6。替换只做 JSON.parse 的旧 readLayout；标准 JSON/Number 检查即可完成，无新依赖。

仅接受对象根及 compact/expanded 对象模式。x/y 接受有限数值，允许屏幕变化前的负坐标，由既有定位约束处理；width 接受 160–600 的有限数值，覆盖现有预设/拖拽范围；edge 只接受 left/right。非法字段独立丢弃，其他有效字段保留，无有效字段的模式省略。数组、标量、解析/读取失败回退空布局；不保留未知键，也不将数字字符串隐式转为尺寸。

读取本身不重写存储，后续用户布局操作仍走既有保存路径。旧 POSITION_KEY 的迁移入口保留，本轮不将其宣称为已替换；实际 viewport 限制仍由布局函数处理。

## 验证

- verify_layout_data.cjs 实现前缺文件失败，之后覆盖非法 JSON、根/模式类型、边界宽度、有限坐标、左右边缘、未知键及有效模式保留。
- verify_mount 在旧候选用非数字宽度复现 style.width 为空；新候选 Chromium/WebKit 挂载后回退 292px 且内存布局为空，既有设置回归通过。
- verify_docking 双浏览器左右有效布局、折叠、尺寸与位置重置回归通过。Python 3.9.6 / 3.14.3 各 120 项通过。

候选 /tmp/quota-layout-data-candidate。证据为隔离合成浏览器与单元检查，不是原生、Windows 或发行验收；现用安装与真实偏好未动。保留几何、模板与伴宠代码继续归因并携带 LICENSE/NOTICE。
