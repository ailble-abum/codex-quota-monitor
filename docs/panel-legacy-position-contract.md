# V2 旧位置记录迁移

2026-09-20，接续 3eff364。用 initialPanelLayout 替换保留布局函数中的初次读取与旧位置迁移块，复用前轮 readLayout 校验。只在当前实例尚无布局时执行。

优先使用有效新 compact 布局，包括仅含有效宽度的模式；缺少有效 compact 时读取旧 POSITION_KEY。旧记录必须为非数组对象，left/top 分别只接受有限数值，映射到 x/y；无有效坐标时不生成 compact。旧读取/解析失败不影响新 expanded，坏的新 compact 可由有效旧坐标回退。读取和迁移均不写回或删除存储，后续布局保存仍沿用既有路径。

## 验证

- verify_layout_data.cjs 新增迁移测试在实现前缺函数失败；实现后通过无效记录、部分合法坐标、优先级、非法新布局回退、旧解析失败等情形。
- verify_mount 在旧候选复现字符串/null 坐标进入内存 compact；新候选 Chromium/WebKit 挂载后保持空布局并使用默认宽度，既有设置回归通过。
- verify_docking 双浏览器左右停靠、折叠、尺寸与重置回归通过。Python 3.9.6 / 3.14.3 各 120 项通过。

候选 /tmp/quota-legacy-position-candidate。验收为隔离合成浏览器与单元检查，不等于原生、Windows 或发行验收；现用安装和真实位置记录未动。剩余几何、模板和伴宠实现仍保留归因及 LICENSE/NOTICE。
