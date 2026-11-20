模型接入统一使用 DeepSeek 官方 API。用 Python 的 openai SDK 调用

client.chat.completions.create，配置从 .env 读取：



DEEPSEEK\_API\_KEY=你的密钥

DEEPSEEK\_BASE\_URL=https://api.deepseek.com

DEEPSEEK\_MODEL=deepseek-flash



调用时传入 tools，并设置 extra\_body={"thinking": {"type": "disabled"}}。

每轮保留模型返回的 assistant 消息，执行它请求的工具，再按对应的

tool\_call\_id 回传真实结果，让模型决定下一步。新闻来源沿用 RSS 方案。



请在 .env.example 中保留空密钥占位，把 .env 加入 .gitignore。

