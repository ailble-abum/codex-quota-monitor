# 独立前台运行入口与生命周期

2026-09-20，接续 a016bcb。新增 `python -m quota_monitor.live`；原 `python -m quota_monitor PATH --thread ID` 离线预览接口保持不变。没有安装守护进程、启动/重启宿主、扫描调试端口或改动现用监视器。

## 复用与来源

复用 V2 UpdateLoop 的目标选择、数据读取与面板协议，仅在外围增加前台配置、诊断和终止策略。使用标准库 argparse/json/asyncio/signal，不增加生产依赖；CDP 仍使用已固定的可选 websockets。没有复制旧启动器或旧监视循环。

2026-09-20 核查 [Python Task 取消](https://docs.python.org/3/library/asyncio-task.html#task-cancellation)、[CancelledError](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError) 与 [signal.signal](https://docs.python.org/3/library/signal.html#signal.signal)：主解释器主线程安装信号处理器，在取消后用 finally 清理。这里由进程入口将取消转换为退出码，底层 CDP/UpdateLoop 原有取消传播保持不变。Windows 信号支持有限，本轮没有 Windows 真机证据。

不引入进程管理框架或服务安装库：单一前台任务的退出和重试可直接由标准库实现。系统级自启动/安装不是本轮交付。

## 显式配置

```json
{
  "origin": "http://127.0.0.1:9222",
  "page_url": "about:blank",
  "journals": {"one": "one.jsonl"},
  "host": "explicit",
  "panel": false
}
```

示例仅描述协议，运行时必须换成调用方自己授权的隔离目标。origin/page_url 必填，journals 与 session_root 必选其一（见[受限目录关联](directory-index-contract.md)）；host 默认 explicit，另支持 codex-sidebar；panel 默认 false。页面/面板协议见 [宿主与面板契约](host-panel-contract.md)。panel=true 要求目标已挂载消费者 hook；命令不自动注入旧 renderer。

配置文件最大 64 KiB；1–256 个任务映射；重复键、未知字段、非法任务 ID、错误类型、非回环 origin 均拒绝。任务 key 必须是无 local: 前缀的规范 ID，日志中的 session_meta 继续核对该身份。日志相对路径相对于配置文件所在目录；绝对路径也可显式提供。不会据此扫描父目录、读取认证或推断其他会话。

```sh
python -m quota_monitor.live --config /absolute/synthetic/config.json --once
python -m quota_monitor.live --config /absolute/synthetic/config.json --interval 1 --max-failures 5
```

帮助和原离线入口不加载可选 CDP 依赖。依赖缺失返回 dependency_unavailable，不自动 pip install。

## 状态与退出

- stdout 是逐行 JSON：状态改变才输出 `{ "event": "state", "status": "updated" }`。相同状态的持续轮询不反复打印，不调用模型。诊断不输出日志正文、任务 ID、路径、URL 或私密异常内容。
- updated 表示该次快照被页面接受，可能是用于清空的空摘要；不是日志完整/账户可用/安装成功的证明。unselected 表示没有合法活动任务；changed 表示读写期间任务改变。
- updated/unselected/changed 视为连接链正常，重置连续失败计数。目录来源的 data_* 状态也重置失败计数，含义见目录契约。其他状态计入连续失败；默认 5 次后停止。失败间隔为 interval、2×interval、4×interval…，最多 60 秒；恢复后回到原间隔。interval 允许 0.1–60 秒，失败上限允许 1–100。
- --once 执行一轮并立刻走释放流程：updated 返回 0，其他结果返回 2。它是一次连接/投影检查，不用于把快照永久留在页面。
- 常规退出码：0 单次成功；2 配置/参数/依赖错误、单次未发布或连续失败上限；3 未预期运行/清理错误；130 SIGINT；143 SIGTERM。
- SIGINT/SIGTERM 只取消本进程拥有的协程，信号处理器在清理后恢复；不会杀死或重启宿主。进入清理阶段后，信号只更新退出原因，不再取消清理；包括 --once 边界刚排队的取消。重复信号不反复打断第一次清理。若强制 SIGKILL，则不会执行 Python finally，仍依赖页内租期。
- 终止输出 `{ "event": "stopped", "reason": "sigterm", "cleanup": "released" }`。reason 还可为 once、failure_limit、sigint、cancelled、error。异常详情只输出固定错误代码。

## 页面所有权与释放

每个 UpdateLoop 有独立随机 owner，发布时记录到自己的转发器。invalidate/release 必须匹配 owner；旧实例退出不会清除其他实例随后发布的数据。这是释放保护，不是多实例并发调度支持；同一页面仍应只有一个更新拥有者。

UpdateLoop.shutdown 在现存连接上请求 release：失效并清空本轮数据、停止本轮定时器、删除本轮快照/转发器属性，然后关闭 WS。没有现存连接时不为了清空而重新发现或重连，也不改变其他页面。

cleanup 含义：

| 值 | 证据与边界 |
| --- | --- |
| closed | 本实例没有成功发布过快照，连接已关闭 |
| released | 页面已确认释放请求；另一个 owner 的状态会被保留 |
| lease_pending | 曾发布但已断连、取消发生在收发途中，或页面释放失败；无法确认即时清空，依赖已有 120 秒租期/消费者恢复 |
| cleanup_failed | 清理出现未预期异常；只报告固定错误码，不输出异常正文 |

close 仍保持底层“仅关闭连接”的原语；不改变其他库调用方的行为。前台入口在 finally 使用 shutdown。页面冻结/调度节流时无法承诺实时清空，和上一阶段租期契约一致。

## 验证

```sh
python -m unittest discover -s tests -q
node tools/verify_bridge.cjs
PYTHON=/path/to/python node tools/verify_cdp.cjs
PYTHON=/path/to/python node tools/verify_live.cjs
```

Node 使用已有 Playwright，通过 NODE_PATH 指向既有 node_modules；没有新增浏览器生产依赖。

- Python 3.9.6 / 3.14.3 全套 102 项：保留原离线回归；覆盖配置/参数/依赖脱敏、重复键、实际 HTTP 失败重试间隔/次数、状态去重、POSIX SIGTERM 子进程退出、异常清理、--once 清理边界信号竞态与信号处理器恢复。断连测试使用自己保留的回环端口或自建 HTTP 服务，不访问现用调试端口。
- 临时 Chromium 运行真实 `python -m quota_monitor.live` 子进程：合成日志值 250、刷新后 unselected→恢复、SIGINT/SIGTERM 后页面输出清空且两项全局属性删除、--once 成功后释放、浏览器退出后失败限额结束且只报告一次相同错误。
- Chromium/WebKit 页内协议验证释放匹配 owner；其他 owner 的释放请求不删除现有快照。原 CDP 连接、切换、过期、面板深浅主题回归继续保留。
- CLI 验证中的消费者是合成 output 元素，不能当作完整产品面板或原生应用验收。所有新浏览器、profile、日志和子进程在各脚本 finally 中关闭/清理。

## 接续边界

已具备独立、显式配置的前台运行入口；真实宿主窗口仍未接入，现用安装保持不变。仍需完成受限生产会话关联、消费者初始化/来源替换、原生隔离验收，以及后续安装/Windows/发行工作。受限目录关联已在后续[目录索引阶段](directory-index-contract.md)实现并以合成数据验证；后续优先补齐独立消费者初始化。
