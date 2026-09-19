# 独立 CDP 通信层

2026-09-20。仅在 V2 实现显式页面端点的通信，未接入现用 Codex、扫描调试端口、重启应用或替换旧安装。

## 选型与来源

采用可选依赖 websockets==15.0.1，原日志/离线预览链仍仅依赖标准库。核查来源：

- [版本元数据](https://pypi.org/project/websockets/15.0.1/)：Python >=3.9、BSD-3-Clause，有纯 Python wheel；不是最新发行。选择该版本是为了现有 3.9 基线，不代表后续可永远固定或已通过安全审计。
- [异步客户端官方文档](https://websockets.readthedocs.io/en/15.0.1/reference/asyncio/client.html)：有可取消的收发、消息上限、队列控制、握手/关闭超时；关闭默认代理与压缩。
- [该版本源码](https://github.com/python-websockets/websockets/blob/15.0.1/src/websockets/asyncio/client.py)：核对预连接 sock 在握手重定向时拒绝跟随。使用标准 socket 先连接验证后的回环 IP，再将 socket 交给库，未复制库实现。
- [CDP Runtime.evaluate](https://chromedevtools.github.io/devtools-protocol/tot/Runtime/#method-evaluate)：按协议提供 expression、returnByValue、awaitPromise 与 timeout，并处理 exceptionDetails。
- [许可证](https://websockets.readthedocs.io/en/15.0.1/project/license.html)：通过依赖安装保留包内许可；没有将库源码打包进本仓库。将来做独立安装包时必须连同完整第三方许可证分发。

未采用旧版手写 WebSocket 编解码/握手；不为单一命令引入完整 Playwright 运行时。Playwright 仅用于开发验收。同步 WebSocket 方案本轮不采用，因为希望统一约束 send/recv 并支持取消；这是接口匹配选择，不代表对其他库的全面质量排名。

核查层级：官方文档 + 重定向相关源码 + 本地真实服务/临时 Chromium 实测。未穷尽社区 issue、安全公告、所有打包平台和最新库版本差异，发行前仍需依赖安全与兼容复核。

## 契约

```python
async with CDPClient(explicit_page_websocket_url) as client:
    value = await client.evaluate('({example: 42})')
```

- 只接受 ws + 数字回环 IP + 显式端口 + /devtools/page/ID；拒绝远端域名、凭据、查询、片段及非页面路径。不做目标发现，也不判断该页面是否属于 Codex，调用方负责选择授权目标。
- 不使用系统代理，不跟随握手重定向，不自动重连或重发任何表达式。仅对明确提供的端点创建连接。
- 单事件循环、单拥有者、一个在途 evaluate；并发 evaluate 返回 busy。不要并发进入同一个上下文或从其他任务关闭使用中的实例。
- 默认建立连接与每次完整收发预算 2 秒；关闭握手最多另用 0.2 秒。超时是客户端等待预算，不证明已经发出的脚本没有执行；调用者不可据此自动重试写操作。
- 默认请求和响应大小上限 1 MiB，队列高水位 4，单请求最多处理 128 条消息；非目标响应和事件占用该数量预算。大图像脚本注入尚未验证，不为兼容旧内联图片而默认取消上限。
- 收发/协议/JavaScript 出错或取消后关闭连接；取消继续向调用方传播。发送前的 busy、表达式类型与请求过大检查不关闭连接，也不发送请求。公开错误为固定代码，不拼接脚本、服务端异常正文或 endpoint；内部 WebSocket logger 禁用。
- 返回 JSON 值；undefined 映射 None，无法按值返回的对象/特殊值为 unsupported_value。消息不是字典、ID 类型不正确、非有限 JSON 数字等为 protocol_error。
- 这是具备执行能力的 CDP 客户端，不是任意表达式的“只读沙箱”；生产消费者必须固定表达式边界，不将不可信正文拼接执行。

## 安装与验证

推荐独立虚拟环境，不改系统 Python：

```sh
python3 -m venv /absolute/path/to/test-venv
/absolute/path/to/test-venv/bin/python -m pip install -r requirements-cdp.txt
/absolute/path/to/test-venv/bin/python -m unittest discover -s tests -q
PYTHON=/absolute/path/to/test-venv/bin/python node tools/verify_cdp.cjs
```

最后一条需要已有 Playwright 和 Chromium，NODE_PATH 配置同 [面板探针](panel-probe.md)。它创建临时浏览器及临时 profile，端口由浏览器分配，只读取该 profile 的 DevToolsActivePort，再按唯一合成页面标题选目标。结束后关闭浏览器、清理该次创建的 profile，不访问真实应用配置。

本轮使用 /tmp/quota-cdp-env.MJ3TIY/py39 与 py314 临时虚拟环境，Python 3.9.6/3.14.3 全套 85 项通过。13 项新增连接相关测试（其中 11 项使用真实回环 WebSocket 服务）覆盖 ID/事件、超时、不重发、断连、取消、重定向、错误脱敏、非法端点、过量消息、过大消息/请求和并发拒绝；另验证浏览器探针拒绝 Python -O，避免断言被关闭后假通过。

临时 Chromium 实际通过：返回对象、页面计数连续更新、JavaScript 异常、显式重新连接后读取同一计数、undefined。不是 macOS Codex 原生验收、Windows 真机或安装包验收。

下一步实现明确的页面目标选择与连接生命周期，再接入增量数据更新；不能直接将当前全目录发现器用于高频生产轮询。原启动器、派生注入胶水与完整消息级数据仍待替换，旧归因继续保留。
