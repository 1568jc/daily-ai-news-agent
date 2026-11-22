# 每日 AI 新闻助手 Agent

一个基于 DeepSeek Function Calling 的个性化新闻简报应用。用户可以配置关注话题、中英文关键词和收件邮箱，由 Agent 获取 RSS / Atom 新闻材料，生成最多 5 条中文简报，并支持历史版本、邮件投递和每日定时执行。

真实模式下，Agent 根据每次工具调用的返回结果，自主决定下一步操作，而不是执行写死的新闻处理流水线。只有 `submit_brief` 提交并通过校验后，任务才会结束。

## 功能特性

- **用户与订阅管理**：支持用户查询、创建、修改和删除；每个用户可以独立配置话题、关键词和收件邮箱。
- **自主工具调用**：DeepSeek 通过 Function Calling 选择工具和参数，系统提供 7 个受约束的工具，并记录真实调用参数、返回结果和耗时。
- **个性化新闻简报**：从 12 个 RSS / Atom 来源获取材料，优先筛选最近 24 小时的内容；没有当日更新时，可提供明确标注的最近 7 天补充简报，最多 5 条并附真实来源链接。
- **历史与版本管理**：按日期切换简报；重新生成时保留旧正文、运行记录和工具轨迹。
- **重复操作保护**：同一用户同一天重复执行普通生成时复用已有简报，不重复运行 Agent 或投递邮件。
- **独立生成与投递**：重新生成会创建新版本；再次发送只投递当前简报，不重新调用模型。投递失败后可以重试。
- **可调整的工作台**：后台执行任务，局部更新进度并保留滚动位置；支持历史标签切换、双栏拖拽和窄屏自适应布局。
- **邮件与定时任务**：支持管理员统一配置 SMTP，默认每天北京时间 08:00 执行。

## 技术栈

- 后端：Python 3.11+、FastAPI、Uvicorn
- 页面：Jinja2、原生 JavaScript、CSS
- 数据与调度：SQLite、APScheduler
- 模型与新闻：OpenAI Python SDK、DeepSeek API、RSS / Atom
- 邮件：Python SMTP、STARTTLS

## 快速开始

### 1. 获取项目

```bash
git clone https://github.com/1568jc/daily-ai-news-agent.git
cd daily-ai-news-agent
```

私有仓库需要相应的 GitHub 访问权限。

### 2. 安装并启动

Windows PowerShell：

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python -m app.main
```

macOS / Linux：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m app.main
```

打开 <http://127.0.0.1:8000>。健康检查地址为 <http://127.0.0.1:8000/health>。

默认启用**离线样例模式**，无需 API Key、SMTP 或外网即可体验完整交互。页面和简报会明确标注离线样例与测试替身，不会将其标记为真实模型运行结果。

服务需要保持运行，定时任务才会触发。请使用上述单进程启动方式，不要开启 reload 或多个 worker。

## 使用说明

### 用户与订阅

1. 创建用户，填写昵称、收件邮箱、关注话题和中英文关键词。
2. 在左侧用户列表选择用户，可按昵称或邮箱进行模糊查询。
3. 选中用户后可以修改资料和订阅，也可以删除用户。
4. 删除操作需要二次确认，并级联删除该用户的订阅、简报、历史版本和工具记录。仍有任务执行时需要等待任务结束。

离线样例模式下，可以点击“一键准备三位演示用户”，快速查看同一批新闻面向不同订阅生成的个性化结果。新建用户时也可以选择从空 `news/` 目录开始，观察 Agent 获取材料的过程。

### 生成、重新生成与重发

- **立即生成并预览/推送**：生成当天简报；配置 SMTP 后会尝试投递。同一天重复操作会明确提示，不重复生成或发送。
- **重新生成并预览/推送**：再次调用模型和新闻源，生成新版本，并保留旧版本。配置 SMTP 后可能再次投递，因此需要手动确认。
- **再次发送此简报**：只重新发送当前内容，不生成新简报。投递失败时也可以只重试邮件。

未配置 SMTP 时，系统只生成本地预览，不会显示为已发送。新闻来源失败与确实没有匹配新闻会分别显示。

### 简报工作台

- 右侧区域直接展示当前简报，通过日期标签切换历史简报。
- 展开“本次工具调用”可查看工具顺序、参数、返回结果和耗时。
- 重新生成前的正文和工具轨迹保存在历史版本中。
- 桌面端可以拖拽双栏分隔条调整宽度，设置会保存在浏览器中；窄屏自动切换为上下布局。
- 任务执行期间页面每 2.5 秒局部更新，不整页刷新，也不会主动重置窗口或简报的滚动位置。

### 每日定时任务

默认每天北京时间 **08:00** 执行，与手动生成共用任务入口和每日重复保护。可通过以下配置调整时间：

```dotenv
AINEWS_DAILY_HOUR=8
AINEWS_DAILY_MINUTE=0
```

## 配置真实 DeepSeek 与 RSS

编辑项目根目录的 `.env`：

```dotenv
AINEWS_DEMO_MODE=false
DEEPSEEK_API_KEY=你的真实密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
AINEWS_NOW=
```

保存后重启服务。真实模式从空材料目录开始，由 Agent 选择来源并调用工具。每轮模型调用都提供工具定义，并传入：

```python
extra_body={"thinking": {"type": "disabled"}}
```

当前提供 12 个新闻来源，Agent 会根据用户话题和来源类别自主选择，通常抓取其中 3～5 个，而不是固定遍历全部来源：

- [OpenAI News](https://openai.com/news/rss.xml)
- [Hugging Face Blog](https://huggingface.co/blog/feed.xml)
- [Google DeepMind Blog](https://deepmind.google/blog/rss.xml)
- [Google AI Blog](https://blog.google/technology/ai/rss/)
- [Microsoft Research Blog](https://www.microsoft.com/en-us/research/feed/)
- [AWS Machine Learning Blog](https://aws.amazon.com/blogs/machine-learning/feed/)
- [GitHub AI & ML Blog](https://github.blog/ai-and-ml/feed/)
- [TechCrunch AI](https://techcrunch.com/category/artificial-intelligence/feed/)
- [MIT Technology Review AI](https://www.technologyreview.com/topic/artificial-intelligence/feed/)
- [arXiv cs.AI](https://rss.arxiv.org/rss/cs.AI)
- [arXiv cs.LG](https://rss.arxiv.org/rss/cs.LG)
- [arXiv cs.CL](https://rss.arxiv.org/rss/cs.CL)

正常简报只收录过去 24 小时内的新闻。如果已抓取材料中没有任何 24 小时候选，Agent 可以使用 `recent_fallback=true` 提交最近 7 天内的最多 5 条补充内容；网页、邮件和备注会明确标注“近期补充”和“非今日新闻”。超过 7 天的材料仍不能提交，也不能在存在当日新闻时启用补充模式。

RSS 提供标题、日期、链接和来源摘要等材料，不代表抓取了每篇新闻的全文。实际可用性取决于网络、新闻来源和模型服务。

单个来源会在配置的超时预算内对临时网络或 XML 解析异常最多重试一次。合法但为空的订阅按“成功、0 条”处理；持续不可用的来源会保留明确错误，其他可用来源仍可继续生成简报。

其他常用配置：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `AINEWS_DB` | `data/ainews.db` | SQLite 数据库路径 |
| `AINEWS_TASK_DIR` | `data/tasks` | Agent 任务工作区 |
| `AINEWS_MAX_ROUNDS` | `12` | 单次任务最大模型轮次 |
| `AINEWS_AGENT_TIMEOUT_SECONDS` | `240` | Agent 任务超时时间 |
| `AINEWS_NEWS_TIMEOUT_SECONDS` | `15` | 单个新闻来源请求超时时间 |
| `AINEWS_NOW` | 空 | 固定带时区的样例时间，真实模式保持为空 |

## 邮件投递设置

普通用户只需在自己的订阅中填写收件邮箱。SMTP 是整个系统共用的发件账户，由管理员统一配置。

1. 打开页面右上角的“邮件设置”，或访问 <http://127.0.0.1:8000/email-settings>。
2. 填写 SMTP 服务器、端口、登录账号、发件邮箱和授权码。
3. 保存后立即生效，无需重启服务。
4. 返回用户页面生成简报，或对已有简报执行发送。

QQ 邮箱示例：

```text
SMTP 服务器：smtp.qq.com
端口：587
登录账号：完整 QQ 邮箱地址
发件邮箱：完整 QQ 邮箱地址
SMTP 授权码：QQ 邮箱设置中生成的授权码，不是 QQ 密码
加密方式：勾选 STARTTLS
```

当前使用 `587 + STARTTLS`，不支持直接使用 SSL 465。授权码不会在页面回显；修改其他设置时留空即可保留原授权码。授权码不会进入 Agent 工作区或工具日志。

`.env` 中的 `SMTP_*` 可作为备用配置；网页保存过设置后，以网页配置为准。清空 SMTP 服务器和发件邮箱后保存，即可关闭投递并恢复“仅预览”。

程序先保存成功生成的简报，再尝试投递。状态包括“仅预览”“已投递”“投递失败”和“来源失败”。

## 运行测试

Windows PowerShell：

```powershell
.venv\Scripts\python -m unittest discover -v
```

macOS / Linux：

```bash
.venv/bin/python -m unittest discover -v
```

测试完全离线，主要覆盖：

- Agent 根据工具结果调整后续调用、工具调用 ID 对应关系和提交结束条件；
- 有材料读取、空目录补抓、24 小时窗口和最多 5 条新闻校验；
- 文件路径隔离、只读 `wc` 白名单和英文忽略大小写搜索；
- 每日重复保护、历史版本、来源失败、邮件失败与已有简报重试；
- 用户管理、订阅页面、调度器启动和前端异常状态。

## 项目结构

```text
app/
├── agent.py          # Agent 主循环与工具调用协调
├── tools.py          # 7 个工具的定义、参数校验与执行
├── news.py           # RSS / Atom 抓取、材料处理和新闻校验
├── llm.py            # 通过 OpenAI SDK 接入 DeepSeek
├── demo_llm.py       # 明确标注的离线模型测试替身
├── service.py        # 生成、保存、投递、重新生成与重试
├── database.py       # SQLite 数据结构与每日唯一约束
├── scheduler.py      # 每日定时任务
├── main.py           # FastAPI 路由与应用生命周期
├── templates/        # 页面模板
└── static/           # 样式与前端交互
tests/                # 离线自动化测试
.env.example          # 环境变量示例，不含真实凭据
requirements.txt      # Python 依赖
```

任务工作区位于 `data/tasks/<用户>/<日期与运行ID>/`，包含偏好、来源、近期简报索引、新闻材料和最终提交。数据库默认为 `data/ainews.db`。运行数据、虚拟环境和 `.env` 均已被 Git 忽略。

## 部署与安全注意事项

- 当前版本未实现登录鉴权，适合本地或受信环境使用，不应直接暴露到公网。
- 邮件设置保存在本地 SQLite 中。公网部署应增加管理员鉴权，并使用加密凭据存储。
- 请妥善保管 `.env` 和 SMTP 授权码，不要提交到 Git 或发送到 Agent 工具中。
- APScheduler 在单进程内运行；进程停止期间不会生成简报，也未实现分布式调度或错过任务的补跑。
- 离线测试可以验证应用逻辑，但不能保证真实 DeepSeek、RSS 或 SMTP 服务始终可用；这些外部链路需要有效凭据和网络环境。
