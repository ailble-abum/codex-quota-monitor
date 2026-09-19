# 增量读取器交付记录

## 范围

2026-09-20 用户确认继续最小替换，先实现独立日志读取器。它尚未替换旧版 inspector，也没有接入真实会话、桌面或安装服务。

输入为调用方明确指定的 UTF-8 JSONL 普通文件，单实例串行调用 `JournalReader.poll()`。每次最多读取 read_budget 字节（默认 256 KiB）；每条记录最多 line_limit 字节（默认 1 MiB）。超过限制的行跳过一次并计错，直到换行恢复。空行忽略，非对象 JSON、编码错误、非有限数值和递归解码失败计错。末尾未结束的行等待后续换行，不提前提交。

输出 ReadBatch 包含 records、bytes_read、invalid_lines、reset、more、status。more 表示采样文件大小以内尚有未读取字节，不代表没有待补全半行。初次读取 reset=false；文件身份改变或观测到截断时 reset=true，消费者必须先清除旧会话状态再应用同批记录。打开/读取失败返回 unavailable，保留游标与半行以便重试，不回显异常中的路径或原文。

records 为内部原始输入，可能包含正文，不能直接作为公开快照；后续归约器必须按字段白名单裁剪。repr 不包含 records。本模块不写盘、不联网、不打印日志。

## 来源和复用选择

采用 Python 标准库 json、os、dataclasses、pathlib；不引入第三方尾随读取库。理由是所需文件游标、限额、恢复语义可通过标准接口直接实现，部署无需依赖安装。核查日期 2026-09-20：

- https://docs.python.org/3.9/library/json.html ：已核对 JSON 解码和 parse_constant 接口；文档提醒限制解析规模。
- https://docs.python.org/3.9/library/os.html#os.fstat ：已核对文件描述符元数据接口。

以上为官方接口文档依据；代码按本契约新写，未复制旧解析器。本 Agent 曾检查旧项目，不能据此声称严格洁净室隔离。软件全部来源和发行许可审计仍未完成。

## 验证

`/usr/bin/python3 -m unittest discover -s tests -v`：Python 3.9.6，15 项通过。
`python3 -m unittest discover -s tests -q`：Python 3.14，15 项通过。

覆盖追加、空闲、UTF-8 拆分、半行、坏行、超长行、读取预算、同长度文件替换、截断、暂时丢失再恢复、CRLF、非有限数、双实例和 POSIX FIFO。溢出指数案例先观测失败，再补有限数校验后通过。

一次 Python 3.9.6 合成测试：100,000 条、2,900,000 字节，约 1.021 秒，tracemalloc 峰值 7,252,130 字节；开启跟踪会影响速度，不作为性能承诺。空闲轮次读取 0 字节；追加 29 字节后仅读取 29 字节。非真实会话或原生 UI 验收。

## 已知边界与下一步

- 同 inode 在两次采样间截断并重新增长至原长度或更大、以及原位改写，不能保证识别；输入契约是追加日志。并发写入/轮换不能视为事务快照。
- 不支持多个线程同时调用一个 reader，不持久化游标，不处理压缩日志。
- Windows 非阻塞标志不可用时普通文件读取仍可用，尚未做 Windows 真机验收。
- 下一步依据官方事件结构实现白名单会话归约器，验证 token 去重、未知字段、累计回退与模型切换，再适配旧版 payload 消费者。未完成整个 inspector 替换。
