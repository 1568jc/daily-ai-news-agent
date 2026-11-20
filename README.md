# 每日 AI 新闻助手 Agent

一个可本地运行、可演示的面试项目。用户设置关注话题和中英文关键词，Agent 通过 RSS / Atom 材料生成最多 5 条个性化中文简报，保存历史并投递邮件。

**核心不是固定流水线：真实模式下，DeepSeek 根据每次工具返回的真实结果，自主决定下一次工具调用、补抓次数和结束时机。** `submit_brief` 成功后循环才结束。

## 快速启动（Windows PowerShell）

要求 Python 3.11+。

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python -m app.main
```

打开 <http://127.0.0.1:8000>。默认是**离线演示模式**，无需 API Key、SMTP 或外网。服务需保持运行，定时任务才会触发；请使用上述单进程启动方式，不要开启 reload 或多 worker。

macOS / Linux 将虚拟环境 Python 路径换成 `.venv/bin/python`，并用 `cp .env.example .env`。

## 三分钟面试演示

### 场景 A：同一批新闻，两种订阅

1. 点击首页“**一键准备三位演示用户**”。
2. 查看“演示甲·编程”和“演示乙·研究”：两者都读取 `news/demo_existing.json`，但选题和匹配理由分别面向编程工具与 AI 研究。
3. 展开“本次工具调用”，指出顺序、参数、真实返回值和耗时来自 `tool_calls` 表，而不是展示一段伪造文本。
4. 页面和简报均标注“演示样例 / 离线测试替身”，不会冒充真实新闻或真实 LLM 运行。

### 场景 B：已有材料与缺少材料

1. 甲、乙的任务预置了相同材料。
2. 丙的 `news/` 初始为空。展开丙的工具记录，可以看到模型测试替身依据空目录结果调用 `fetch_news`，再读取返回的材料路径并提交。
3. 新建用户时也可勾选“从空 news/ 目录开始”；该选项只对尚未生成当日简报的新任务有效。
4. 样例时间根据演示时钟动态生成，不会因存放几天而失效。可用 `AINEWS_NOW` 固定带时区的演示时间。

### 场景 C：重复触发与异常

1. 对同一用户连续点击“立即生成并预览”：数据库以“用户 + 北京日期”唯一约束复用同一份简报，不重复运行或投递。
2. 未配置 SMTP 时明确显示“仅预览”，不会标记为已发送。
3. 运行下面的离线异常测试：来源失败不会产生“今日无新闻”的正常简报；SMTP 失败会保留正文，重试只发送已有简报，不重新运行 Agent。

```powershell
.venv\Scripts\python -m unittest tests.test_service.BriefServiceTests.test_source_failure_does_not_create_or_send_normal_brief tests.test_service.BriefServiceTests.test_delivery_failure_retries_saved_brief_without_regenerating tests.test_web.WebTests.test_source_failure_is_shown_without_email_preview -v
```

## 切换真实 DeepSeek + RSS 模式

编辑 `.env`：

```dotenv
AINEWS_DEMO_MODE=false
DEEPSEEK_API_KEY=你的真实密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
AINEWS_NOW=
```

重启服务后创建订阅并点击“立即生成并预览/推送”。任务在后台执行，页面每 4 秒自动刷新状态；生成过程中仍可查看已执行的工具记录。每轮模型调用均传入 `tools` 和：

```python
extra_body={"thinking": {"type": "disabled"}}
```

真实模式从空材料目录开始，由模型选择来源。当前配置：

- OpenAI News：`https://openai.com/news/rss.xml`
- Hugging Face Blog：`https://huggingface.co/blog/feed.xml`
- Google DeepMind Blog：`https://deepmind.google/blog/rss.xml`
- arXiv cs.AI：`https://rss.arxiv.org/rss/cs.AI`

本次开发环境已实际访问并解析这四个地址，均能获得带标题、日期和原文链接的条目；后续可用性取决于网络和来源方。RSS 只提供材料，摘要是基于来源文本生成的，不代表已抓取每篇新闻全文。

### 邮件推送

SMTP 留空就是本地预览。需要真实投递时配置：

```dotenv
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=你的账号
SMTP_PASSWORD=你的授权码
SMTP_FROM=news@example.com
SMTP_USE_TLS=true
```

程序先保存成功生成的简报，再投递。状态包括“仅预览”“已投递”“投递失败”“来源失败”等；来源失败与确实没有匹配新闻不会混为一谈。

## 运行测试

```powershell
.venv\Scripts\python -m unittest discover -v
```

测试完全离线，覆盖：

- 模型根据实际工具结果改变后续调用，以及 `tool_call_id` 对应关系；
- 有材料直接读取、空目录补抓、未提交不能结束；
- 新闻 ID、24 小时窗口、5 条上限、来源与 URL 回填；
- 文件路径隔离、只读 `wc` 白名单、英文忽略大小写搜索；
- 个性化样例、每日幂等、来源失败、邮件失败及已有简报重试；
- 订阅页面、生成历史、调度器启动和前端异常状态。

## 代码导览

- `app/agent.py`：**Agent 主循环**。保留 assistant 消息，执行模型请求的工具，按 `tool_call_id` 回传结果，成功提交后结束。
- `app/tools.py`：七个工具的 schema、注册与执行；文件限定在当前用户任务目录，shell 仅允许只读 `wc`。
- `app/news.py`：RSS / Atom 抓取、演示材料、URL 规范化、新闻 ID 和最终提交校验。
- `app/llm.py`：DeepSeek 官方 API 的 OpenAI SDK 接入。
- `app/demo_llm.py`：明确标注的确定性测试替身，仅用于离线演示和测试。
- `app/service.py`：手动按钮与定时任务共用的任务入口；生成、保存、投递和重试。
- `app/scheduler.py`：APScheduler 入口，默认每天北京时间 08:00。
- `app/database.py`：SQLite schema、每日唯一约束和真实工具执行记录。
- `app/main.py`：FastAPI 路由与单进程生命周期。
- `app/templates/index.html`：订阅、历史简报、邮件预览及工具轨迹页面。

任务工作区位于 `data/tasks/<用户>/<日期与运行ID>/`，包含偏好、来源、近期简报索引、新闻材料和最终提交。数据库默认为 `data/ainews.db`。运行数据和 `.env` 均被 Git 忽略。

## 验证边界

离线测试和真实 RSS 解析可以在无凭据时验证。**真实 DeepSeek 工具调用及真实 SMTP 投递仍需要有效凭据后验证**；离线测试替身通过不代表这两条外部链路已实测。

这是本地面试项目，未实现登录鉴权，不应直接暴露到公网。APScheduler 在单进程内运行，进程停止期间不会生成简报，也未实现分布式调度或错过任务的补跑。
