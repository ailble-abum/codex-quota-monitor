# Renderer 首次拆分：视图与宿主扫描分离

2026-09-20，接续 2cc83c9。本轮提供可重复生成的隔离派生候选：保留外部面板/伴宠视图，删除其侧栏修改、消息匹配及观察器生命周期，插入 V2 自写的快照适配器。**这是带原许可的中间产物，尚未完成 renderer 来源替换。** 现用安装及旧仓库均未改动。

## 输入与生成

沿用既有 AST 常量读取器思路，使用 Python 标准库 ast/hashlib/json；不执行或 import 外部 Python 模块，不增加 JS AST 框架。工具仅支持已审查的固定提交和六个文件摘要，因此采用固定唯一边界裁剪；不是通用源码转换器。未知版本、边界丢失/重复直接拒绝，不能容错拼接或套用到最新源码。

来源：旧仓库提交 `2705f32a6f080ee1bdbecdc5b43f5fe0f9045eed`，四个 scripts 文件 `context_token_injector.py`、`companion_feedback.py`、`companion_art.py`、`companion_expressions.py`，加仓库根的原 LICENSE/NOTICE。调用方需把这六份冻结输入放入一个独立目录。

```sh
python tools/build_panel_candidate.py /absolute/frozen-input /absolute/new-candidate
```

输出目录必须不存在；输出 `consumer.js`、原样 LICENSE/NOTICE 和 `manifest.json`。清单保存来源提交、全部输入 SHA-256、输出脚本 SHA-256、候选性质和改动说明。使用 manifest.consumer 的 path/sha256 配置现有 V2 前台入口；路径相对于运行配置，不一定相对于清单。构建不会安装、启动或连接应用。

2026-09-20 核对冻结 LICENSE/NOTICE：MIT 保留 Kevin Ke 与 Ailble 的版权行，NOTICE 保留 KevinKE93/Codex-Monitor 来源与 Ailble 修改说明。生成脚本头也保留归因，分发时必须携带完整许可与 NOTICE。V2 仓库只保存生成工具、自写适配器和测试，不纳入外部 renderer/图片。保留来源不代表剩余代码完成原创性鉴定。

## 本轮删除与保留

| 部分 | 候选行为 |
| --- | --- |
| summaryHover/itemChip/itemTitle、旧任务 ID/活动侧栏搜索 | 删除；视图任务 ID 只取 V2 有效快照 |
| 侧栏标题修改、hover 委托与 tooltip | 删除，不改宿主侧栏的 title/tabIndex/内容 |
| applySidebar、assistantNodes、可见文本匹配、详情猜测、applyFooters | 删除，不访问消息正文，不添加消息 token chip/footer |
| clearFooters 到旧初始化尾部：详情调度、applyAll、全页 MutationObserver、旧 runtime reset | 删除；用新适配器驱动视图 |
| 面板样式、显示/布局、伴宠图片与反馈、部分格式化/展示函数 | 原样保留并继续归因；其中共享样式、辅助函数和挂载仍需进一步来源核对 |

新适配器与保留的 applyHud 等函数处于同一闭包，仅接收 `window.__quotaMonitorV2Snapshot` 当前返回的同一个对象。缓存旧对象、复制对象、任务变化或租期失效时，收到的数据被替换为空摘要。视图自己的按钮重绘也经过此检查。V2 页内桥继续负责 250ms 失效检查、任务核对和 120 秒租期；候选不新增宿主观察器或第二套刷新定时器。

候选初始化前拒绝已经存在的根面板、样式或伴宠 DOM，不清除或接管它们。前台入口已有 hook 时仍按已有契约复用，不会热替换；验收必须使用新隔离页面。关闭 runner 清空数据，不等于卸载消费者 DOM/其视图监听器。

## 验证

- 单元测试拒绝未知输入与错误/重复裁剪边界；所有输入先验摘要，再解析/生成输出。
- 从冻结输入真实运行构建命令，核对输出脚本 SHA-256 和 LICENSE/NOTICE。输出未包含旧 activeSidebarRow、assistantNodes、applySidebar、applyFooters、detailForVisiblePage、installObserver 函数及 MutationObserver 构造。
- Chromium/WebKit × 深浅主题：新初始化分支挂载完整候选；上下文数值/详情、任务切换、缺失、过期清空、单实例全部验证。初始化时禁止 MutationObserver，读取合成消息的 textContent/innerText 会抛错；测试通过。侧栏原始属性/内容保持一致；没有消息 footer/chip。
- 旧缓存载荷在切换任务后直接调用消费者仍清空；占位的既有面板初始化时拒绝且内容保持。
- 真实 Chromium CDP × 深浅主题：独立 UpdateLoop → 候选，验证追加、切换、缺失、过期、刷新重新挂载和重复更新。

Python 3.9.6 / 3.14.3 全套各 118 项通过；构建输出摘要、原 LICENSE/NOTICE 一致性与已有目录拒绝覆盖验证通过。

完整候选使用环境变量选择，不影响原外部 renderer 对照路径：

```sh
QUOTA_PANEL_CANDIDATE=/absolute/new-candidate/consumer.js \
  node tools/verify_panel.cjs /absolute/frozen-input /absolute/evidence --bridge
QUOTA_PANEL_CANDIDATE=/absolute/new-candidate/consumer.js \
  node tools/verify_runtime_panel.cjs /absolute/frozen-input /absolute/runtime-evidence
```

脚本使用已有 Playwright（NODE_PATH）和隔离 Python（PYTHON），不安装生产依赖。截图记录于本机 `/tmp/quota-split-panel-evidence` 与 `/tmp/quota-split-runtime-evidence`；WebKit 深浅主题已目视核对，面板设计和数值保持。生成候选位于 `/tmp/quota-split-candidate-2cc83c9`，不是安装包。

## 开放边界

消息级对应与侧栏 tooltip 本轮明确不提供，不以旧正文猜测作为回退。账号配额、历史、伴宠完整交互仍没有生产数据验收。本轮展示继承保留视图，不声称整份脚本独立原创；尚需对共享样式、格式化和 ensureHud 等展示挂载部分逐项追溯/替换，并补齐消费者卸载契约，再安排隔离原生闭环。没有真实用户会话、原生窗口、Windows 或发行验收。
