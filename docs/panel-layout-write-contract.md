# V2 布局写入失败处理

2026-09-20，接续 49ffbe4。生成器移除旧 saveLayout，并将保留的 setLayoutPreset 中直接预设写入改为 V2 setLayoutPreference。沿用标准 Storage/JSON，不增加依赖。

预设写入只接受 mini/standard/large。写入失败时在当前消费者实例保留临时值，按钮选中态与后续刷新读取同一值；成功写入后清除临时值。布局保存捕获序列化及 Storage 异常，返回 false；内存中的 root.__ctiLayout 保留，原有调用继续布局更新，而不被异常中断。成功返回 true。

边界：两个存储键仍独立保存，不提供事务原子性；一个写入成功、另一个失败时，重挂载可能按分别持久化的值恢复。临时预设与未保存几何不跨卸载/重启，也无自动重试。保留调用者不把返回值呈现为已保存提示。位置重置、折叠、其他设置仍有直接存储访问，不能声称全局禁用存储后所有交互均可用。

## 验证

- verify_layout_preference.cjs 新增写入检查在实现前因缺失函数失败，实现后通过临时选择、非法输入、失败后内存几何不变、恢复成功及循环对象序列化异常。
- verify_mount 在旧候选复现同时拒绝两个布局键写入时大字按钮不改变宽度；新候选 Chromium/WebKit 通过实际宽度增大、后续刷新/语言切换仍选大字、持久值保持原样、恢复后标准尺寸与几何落盘，且无页面错误。
- verify_docking 覆盖双浏览器左右停靠、固定折叠往返及视口缩小。Python 3.9.6 / 3.14.3 各 120 项通过。

候选 /tmp/quota-layout-write-candidate，截图 /tmp/quota-layout-write-components 与 /tmp/quota-layout-write-docking。仅为隔离合成浏览器证据，非原生、Windows 或发行验收；现用安装和真实偏好未动。保留几何计算、模板和伴宠代码仍携带来源归因及 LICENSE/NOTICE。下一步处理位置重置及伴宠尺寸事件。
