# V2 面板尺寸预设读取与事件

2026-09-20，接续 bb27042。依据已有 mini/standard/large 三档合约，用原生 Storage 与 DOM 替换尺寸偏好读取及按钮状态投影。生成器删除旧 layoutPreset、updatePresetButtons 和正文内逐按钮 click 监听；面板根委托调用保留的 setLayoutPreset，不增加依赖。

读取缺失、非法或失败时回退 standard，初始化不写偏好。按钮 data-active 与 aria-pressed 共用判断。保留原宽度、位置、停靠计算和保存路径；本轮不是完整布局重写，也没有实现布局写入失败的临时状态，不能将读取容错外推到写入。

## 验证

- verify_layout_preference.cjs 实现前缺文件失败；实现后验证三档、非法/缺失、读取拒绝及按钮选中态与 ARIA 同步。
- verify_mount 在旧候选复现只拒绝尺寸偏好读取时 publish 报 panel consumer unavailable；新候选 Chromium/WebKit 通过回退标准、继续刷新、逐档实际点击保存，且实测宽度 mini < standard < large。
- 既有完整挂载、语言重建、其他偏好、控件与所有权回归继续通过；verify_docking 验证左右停靠、固定折叠往返及视口缩小。Python 3.9.6 / 3.14.3 各 120 项通过。

候选 /tmp/quota-layout-pref-candidate，截图 /tmp/quota-layout-pref-components 与 /tmp/quota-layout-pref-docking。以上为隔离合成浏览器验证，不是原生、Windows 或发行验收。现用安装与真实偏好未改动。布局函数、模板和伴宠仍保留来源归因与 LICENSE/NOTICE；下一步继续处理布局写入和尺寸/位置设置。
