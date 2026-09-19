# V2 配额通知可用性

2026-09-20，接续 13f3a5d。核查 V2 Python/JS 与生成候选未发现配额通知发送链路；旧 data-alerts 开关仅写入 cti-alerts，界面却仍宣称每窗口提醒一次。因此本轮禁用并保持未勾选，不新增通知能力。

固定源生成器校验模板标记仅出现一次后，给复用的 checkbox 添加 disabled 与 aria-describedby，替换旧宣称为中英“配额通知尚未接通”。同时移除该偏好的旧读取和 change 监听，不清空、不迁移原存储值。伴宠本地提示与该系统通知开关是不同接口，本轮未禁用已存在的本地提示。

## 验证

- verify_mount 新增检查在旧候选上因开关仍可操作而失败；新候选 Chromium/WebKit 通过：预置 cti-alerts=true 后仍禁用且未勾选、初始化读取计数为零、存储仍为 true，语言往返保持不可用状态与对应说明。
- verify_panel --bridge 的双浏览器明暗主题、任务切换、缺失/失效数据通过。Python 3.9.6 / 3.14.3 各 120 项通过。
- 已目视核验 WebKit 明暗设置截图，禁用开关和未接通说明可见。候选搜索确认不再含 cti-alerts 读写或每窗口提醒一次的旧文案。

候选 /tmp/quota-alerts-candidate，截图 /tmp/quota-alerts-components 与 /tmp/quota-alerts-panel-evidence。以上为隔离合成浏览器证据，未发送系统通知，也未进行原生、Windows 或发行验收。现用安装、真实偏好未改动；保留资源继续归因并携带 LICENSE/NOTICE。通知能力需要独立的数据、权限及可见通知验收后才能启用。下一步继续处理布局设置。
