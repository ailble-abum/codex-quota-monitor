# 账户读取与本地预览安装

2026-09-20。用户授权先补缺口、本地验收，再上传。现用安装不修改；正式发行尚未通过。

## 接口与复用依据

核查 [OpenAI App Server 官方文档](https://developers.openai.com/zh-Hans/docs/app-server) 的初始化与账户速率限制章节，并检查本机 Codex 的 `app-server --help`。复用官方 stdio JSON 协议，以 Python 标准库 asyncio 驱动，不引入第三方账户 SDK，不复制旧 quota_reader 实现。只发送 initialize、initialized、account/rateLimits/read；不创建模型轮次，不登录、退出或消耗重置额度。

多桶响应只选 codex；缺少该桶时不取其他桶冒充。仅旧格式响应回退 rateLimits。窗口时长保持分钟，缺失 5h 不合成；未知数值不可用。只向 renderer 传递白名单字段，丢弃原始账户、信用额度 ID 和其他未支持字段。保留服务端明确的限额阻断。

配置新增可选 account_cli，必须为本机 Codex 可执行文件绝对路径；省略时保持原行为。后台最多每 60 秒发起一次读取，不阻塞本地会话更新；每次读取 12 秒截止、输出总量和行数有界。失败立即替换旧额度，120 秒过期清空，退出取消任务并回收其子进程。--once 不等待后台账户读取，不能用作账户验收。

## 安装范围

`python tools/install_preview.py CANDIDATE_DIR NEW_DESTINATION` 将 V2 Python/JS、固定 renderer、完整 LICENSE/NOTICE、依赖清单和配置样例放入新的独立目录；校验 renderer 摘要，拒绝覆盖已有目录。安装清单记录每个文件 SHA256。运行不再依赖旧仓库目录，但 renderer 构建仍依赖已固定的外部来源材料；这不表示来源替换已完成。

使用独立虚拟环境安装 requirements-cdp.txt，再运行安装目录的 run.py。配置样例必须填写显式页面 URL 和授权会话目录，可添加 account_cli。不自动发现或重启宿主，不注册服务，不向现用页面叠加第二个监视器。先停止本实例再删除目录即可卸载。

## 验收证据与开放项

新增测试覆盖 stdio 握手、干扰通知、数值校验、多桶选择、输出白名单、超时、缺失 CLI、取消回收、非阻塞读取、过期清空、更新循环发布及关闭；安装覆盖独立运行帮助、保留归因、篡改拒绝和防覆盖。

真实本机 App Server 读取成功，返回一个 10080 分钟窗口。隔离 Chromium 的深浅主题面板通过真实账户读取→V2 更新循环→额度 DOM 检查，并保留合成会话的追加、切换、缺失、过期、刷新与单实例测试。没有将原始账户响应写入仓库。

这些证据不是现用原生窗口验收。原生宿主连接、常驻安装、真实健康/历史/通知、renderer 剩余来源替换和正式上传仍开放；Windows 未验收。

本轮 Python 3.9.6 与 3.14.3 各 130 项测试通过。独立预览已安装到本机 `~/Library/Application Support/CodexQuotaMonitorV2/preview-20260920`，使用自己的 Python 3.9 虚拟环境与 websockets 15.0.1；44 项安装文件摘要核对通过。随后从该安装目录导入运行时、读取该目录 renderer，并使用安装环境重跑 Chromium 深浅主题实际账户联动，均通过。预览未注册常驻服务，未接入现用窗口，未上传。
