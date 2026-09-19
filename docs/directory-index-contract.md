# 受限目录会话关联

2026-09-20，接续 23bc5e1。独立前台入口现在可将配置的 `journals` 替换为 `"session_root": "synthetic-sessions"`。二者必须且只能提供一个；相对路径以配置文件目录为基准。不默认读取用户会话目录，不读取认证，不连接现用安装。

## 复用与核查

复用 V2 的 SessionJournal、增量 JSONL 读取器、身份核对与数值投影，不将原离线 discover 全量读取放入更新循环。新增目录清单缓存，使用 Python 标准库，无新增依赖，也没有复制旧监视器实现。

2026-09-20 核查 [os.scandir](https://docs.python.org/3/library/os.html#os.scandir)、[os.open](https://docs.python.org/3/library/os.html#os.open) 及 [os.supports_dir_fd](https://docs.python.org/3/library/os.html#os.supports_dir_fd)：目录 fd 枚举与相对 fd 打开属于 Unix 能力，O_NOFOLLOW/O_DIRECTORY 必须在平台存在。采用该接口配合现有增量读取器；无需引入跨平台文件监听服务或另一个日志解析库。官方文档核对与本机合成目录验证已完成；没有 Windows 支持声明。

## 预算与一致性

- 完整清单最多 4096 个条目、128 个普通 `.jsonl` 文件、8 层子目录；任一超限返回 incomplete，不能把截断清单当成唯一匹配。
- 每轮所有文件合计最多读取 256 KiB，均分预算，保留增量游标。每个文件仍有 1 MiB 的未完成行上限，128 个文件的待解析字节最坏约 128 MiB，另有解析临时对象。大目录应由调用方明确缩小授权范围；此阶段未做生产规模性能验收。
- 目录设备号、inode、mtime/ctime 不变时不重新枚举。每轮前后检查已知目录；结构变化立即发布空摘要，最多每 30 秒重新扫描一次。新增、删除、重命名会造成等待窗口。
- 只用日志内部 session_meta 关联任务，不靠文件名。所有文件读完后才能确认唯一性；重复身份、缺失/冲突身份、损坏行、未结束行都阻止发布。损坏状态持续到文件替换或可检测的截断重置。
- 本协议沿用 append-only 日志假设，不承诺同 inode 等长原地改写检测，也不提供多文件事务快照；读取之后的新追加在后续轮次处理。
- 枚举跳过符号链接与特殊文件。读取从显式 root 重新打开目录 fd，子路径逐层 O_NOFOLLOW，文件也不跟随链接；缓存子目录被替换为链接不能越界读取。root 本身不能是链接，但 root 之前的系统路径组件可正常解析（如 macOS `/var`）。不宣称防御授权 root 的祖先路径被恶意并发替换。
- 缺少 fd 枚举/相对打开或必要标志时返回 unavailable，不退回不受限字符串扫描。未发现文件或暂时不可读时清空，保留后续恢复机会。

## 运行状态

目录来源未就绪但页面已接受空摘要时，报告 `data_loading`、`data_index_wait`、`data_incomplete`、`data_unavailable`、`data_not_found` 或 `data_ambiguous`。这些状态不消耗 CDP 连续失败预算；只有变化时输出诊断。`--once` 遇到这些状态返回 2，清理仍释放本实例发布的空快照。成功的唯一关联继续报告 updated。

## 验证与边界

`tests/test_indexed.py` 使用临时合成目录，覆盖增量追加不再枚举、全局字节预算、公平推进、结构变更等待/恢复、重复身份、冲突身份、损坏与截断、未完成行、各项扫描上限、子目录/文件/root 链接拒绝、能力缺失拒绝。

`tools/verify_live.cjs` 在临时 Chromium 中运行真实 CLI：随机日志文件名自动关联并显示 250；新增重复文件后报告 data_index_wait、页面立即清空，超过连接失败预算的轮次仍保持运行；SIGTERM 后退出，若恰在 CDP 收发中取消则按既有契约报告 lease_pending（此时页面已是空摘要），否则释放页面；重新启动的 --once 对重复身份返回 data_ambiguous/退出码 2 并释放。重扫描后的 ambiguous 与删除恢复由可控时钟单元测试验证。

本轮 Python 3.9.6 / 3.14.3 全套各 113 项通过；真实 Chromium CDP 回归、CLI 目录场景和 Chromium/WebKit 页内桥回归通过。

没有访问真实会话，没有新增或修改 UI，没有改动现用安装。生产大目录、真实原生窗口、Windows、安装与发行仍未验收。后续[显式消费者初始化](consumer-contract.md)已补齐启动入口；消费者源码替换和隔离原生闭环仍待完成。
