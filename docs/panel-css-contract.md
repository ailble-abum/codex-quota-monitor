# 保留样式的作用范围清理

2026-09-20。继续在独立 V2 生成隔离候选，不修改现用安装。

## 变更及来源

生成器仍只接受 `2705f32a6f080ee1bdbecdc5b43f5fe0f9045eed` 六份输入的既定 SHA256。移除已无 JS 调用路径的 badge、reply footer/chip、sidebar tooltip/credit 样式。保留面板和伴宠视觉资产，不把裁剪或限定范围记为独立创作。

对剩余 13 个裸属性选择器加 `:where(#codex-context-token-inspector-root)` 祖先限制，覆盖标题及其伪元素、更新时间、上下文、详情、皮肤、说明、健康提示及伴宠比例值。`:where` 不增加原选择器优先级。固定模板边界和匹配数量不符时拒绝构建；这不是通用 CSS 转换器。现有 `.cti-*` 类名规则仍保留，尚不保证任意同名类或根 ID 冲突的完整 CSS 隔离。

来源对照：核查 [KevinKE93/Codex-Monitor 固定源文件](https://github.com/KevinKE93/Codex-Monitor/blob/56b2ea3602cf8395bdc9d0513a8088f8e38d657e/scripts/context_token_injector.py)。面板基础规则和 n/pct 等格式函数仍有继承实现。继续携带原 LICENSE/NOTICE；完整 renderer 来源替换和法律结论均未完成。本轮是固定来源资产清理，复用现有生成器及 CSS 标准，不增加第三方依赖。

## 验收

- 新增宿主同名属性探针：旧候选失败，确实改变宿主的光标、间距、字号及伪元素；新候选在 Chromium/WebKit 通过。
- 构建单测覆盖裁剪、零额外优先级前缀、逗号分隔选择器、意外数量和未知模板拒绝。
- Python 3.9.6 / 3.14.3 全套各 120 项通过。
- 挂载、键盘、单位、拖动点击抑制、他人节点保护探针通过；完整 Chromium/WebKit 明暗主题的数值、切换、缺失、过期及单实例探针通过。
- 已目视核对 WebKit 明暗主题截图，面板布局保留。合成浏览器证据位于 `/tmp/quota-css-panel-evidence`，候选及完整归因位于 `/tmp/quota-css-candidate`。这些是临时本机验收材料，不是发行包。

未执行真实原生窗口、真实账户、Windows 或发行验收。下一步处理保留格式化函数及其他展示实现，保留伴宠资产归因。
