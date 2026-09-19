# 会话状态归约器

2026-09-20：独立基础模块，未替换旧版 inspector，未接入真实会话或面板。

## 依据与范围

已核对 OpenAI 官方协议源码中的 TokenUsage、TokenUsageInfo、TokenCountEvent、TurnContextItem：
https://github.com/openai/codex/blob/5ee2bdf1e0e04064bc427ae31a49a01e8f7064df/codex-rs/protocol/src/protocol.rs

仅使用字段与事件契约，不复制其 Rust 实现或旧版解析器。核对时固定上述源码提交；不代表所有桌面版本支持完全相同的事件。实现只消费现有 rollout 类型 turn_context、event_msg/token_count、compacted；尚未消费较新的 thread_settings_applied、token_usage_record 等类型。

采用 Python 标准字典与纯状态归约，无额外依赖。官方结构已经区分累计和最近用量，无需引入统计引擎。协议中允许 info=null 的 token_count，不应因此生成零用量或清空先前快照。

## 行为

- total 与 last 是各自的来源快照，不做求和；重复 token_count 不增加累计。
- Token 接受非负有符号 64 位整数，拒绝 bool、浮点、字符串、负数与溢出；缺失/无效字段为 None。
- 缓存输入和推理输出单列，不额外加入来源 total。
- context_percent 使用最新输入/window；window 缺失或非正时未知。不裁剪大于 100 的读数，以免掩盖来源异常。它是本地指标定义，不是承诺精确的服务端上下文占用。
- turn_context 更新 model/effort；模型变化后清空 last/window，保留累计快照。压缩同样清空上下文并计数，等待新用量，不把压缩摘要长度当 Token。
- 累计 total 回退时采用新快照并增加 counter_resets，不伪造差额，也不宣称确定知道回退原因。
- snapshot 返回独立副本，只输出明确字段；忽略正文、项目路径、会话标识、认证信息和限额载荷。model/effort 仅接受长度受限的标识符格式，这不是任意输入下的秘密探测器。
- SessionJournal 每次有界读取，文件 reset 后先创建新归约状态，再消费本批记录。status=unavailable 时携带最后已知状态；调用方不能将其呈现为新鲜读数。more=true 表示尚未读完本次文件范围，状态可能滞后。

## 验收和限制

Python 3.9.6 与 3.14 下 30 项测试通过（15 项读取器 + 12 项归约器 + 3 项串联）。所有文件为临时合成输入。覆盖重复快照、累计回退、模型切换、压缩、null info、未知事件、缺失/非法计数、字段裁剪、跨读取批次及文件替换。

SessionState 按文件顺序接受事件，不支持乱序重排。压缩按记录计数：底层正常增量读取不重放，但调用方主动重复提交 compacted 会重复计数；缺乏稳定事件 ID 时不擅自将相似压缩合并。

尚缺：当前用户轮次/回复级对应、会话发现与活动任务选择、旧 payload 字段兼容、多会话管理、真实桌面事件样本兼容验收。第一阶段尚未全部完成。下一步先补只读兼容投影及合成消费者测试，再决定旧版接入。
