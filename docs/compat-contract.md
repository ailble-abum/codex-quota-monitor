# 数值兼容桥与离线预览

2026-09-20。范围：新 SessionJournal → 旧面板数值字段；没有替换旧安装，也不是完整 payload_builder 的替代品。

## 消费者依据

读取现有项目 context_token_injector.py 的 summaryHover、itemChip、itemTitle、applyHud 和 inject_once 字段访问点，只依据消费者接口设计投影，不复制旧 payload 组装实现。无需新依赖，使用标准 Python 字典投影。

| 新状态 | 旧字段 | 含义 |
| --- | --- | --- |
| last.input_tokens | latest_context_tokens、latest_turn_input_tokens | 最近请求输入，不是用户整个回合的累计 |
| last 的其他计数 | latest_turn_* | 最近一次用量快照；reasoning_output_tokens 映射 reasoning_tokens |
| total 各项 | session_* | 来源累计快照，缓存/推理不重复加总 |
| window、context_percent | context_window、latest_context_percent | 来源窗口及本地计算比例 |
| model、effort | model、reasoning_effort | 最近模型设置 |

兼容旧字段命名不意味着认可 UI 的“本轮”标签精确等同用户回合。后续接入需要明确该文案，不能把最后一次请求误报为整轮统计。

## 选择与可用性

调用者必须提供已验证的任务与文件对应关系；桥接器不猜文件名、不读取 session_meta、不自动查找其他任务。readings 字典使用规范任务 ID，活动 ID 可有 local: 前缀。

仅发布当前明确选中的任务。原因是旧面板有 summaries[0] 回退行为；缺失活动任务时提供其他摘要会串任务。因此此阶段暂不提供其他会话侧栏摘要与项目排名。

status!=ok 或 more=true 的读数不发布。缺失数值仍为 None，零保留。detail=None、detailsByThread={} 明确表示尚无回复级数据；不编造 hover/footer 或消息匹配结果。未输出配额、历史、健康、版本字段，未来接入必须由原有组件提供，不能直接替换旧 build_payload 后就视为功能对等。

## 离线预览

```sh
python3 -m quota_monitor /path/to/synthetic.jsonl --thread demo
```

命令仅访问显式路径，不扫描真实会话。调用方负责确认 --thread 属于该文件，此参数不是从文件认证出的身份。默认最多 64 次、每次 256 KiB 读取；--max-polls 可在 1..4096 调整。预算耗尽输出 incomplete、空 summaries，退出码 2；不可读输出 unavailable，退出码 2。成功输出 ok，退出码 0。

ok 表示已读完本次可见字节范围，不代表有有效 Token、通过产品验收或末尾半行已提交。半行仍遵循读取器等待换行契约。输出为白名单状态与投影，不含输入路径或会话正文。

## 验证

Python 3.9.6、3.14 均通过 42 项测试，其中新增 8 项字段/选择测试及 4 项真实子进程 CLI 测试。合成日志经过读取器、归约器、投影到 legacy 数值字段；验证预算耗尽、文件不可读和正文/路径裁剪。

尚缺活动任务身份解析与文件发现、消息级详情、旧版 UI 实际接入、深浅主题与原生验收。下一步先实现明确的任务身份解析及受限会话查找，随后在隔离环境替换消费者，保留原有伴宠与配额设计。
