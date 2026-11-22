from __future__ import annotations


def brief_markdown(content: dict) -> str:
    lines = ["# 每日 AI 新闻简报", ""]
    recent_fallback = content.get("content_window") == "recent_7d"
    if content.get("demo_sample"):
        lines.extend(["> 演示样例 / 离线测试替身运行，非真实新闻或真实 LLM 结果。", ""])
    if recent_fallback:
        lines.extend(["> 今日暂无新发布；以下为最近 7 天内的补充内容，非今日新闻。发布日期见各条目。", ""])
    items = content.get("items", [])
    if not items:
        empty_title = "## 最近 7 天也没有匹配的新闻" if recent_fallback else "## 过去 24 小时没有匹配的新闻"
        lines.extend([empty_title, "", content.get("note", "")])
    else:
        for index, item in enumerate(items, start=1):
            lines.extend([
                f"## {index}. {item['title_zh']}",
                "",
                f"**发生了什么：** {item['summary']}",
                "",
                f"**为什么与你相关：** {item['reason']}",
                "",
                f"来源：{item['source']} · {item['published_at']}",
                f"[阅读原文]({item['url']})",
                "",
            ])
        if content.get("note"):
            lines.extend(["---", "", content["note"]])
    return "\n".join(lines).strip() + "\n"


def brief_subject(brief_date: str, content: dict) -> str:
    prefix = "[演示] " if content.get("demo_sample") else ""
    if content.get("content_window") == "recent_7d" and content.get("items"):
        suffix = f"近期补充 {len(content['items'])} 条"
    else:
        suffix = "无匹配新闻" if not content.get("items") else f"{len(content['items'])} 条精选"
    return f"{prefix}每日 AI 新闻简报 {brief_date} · {suffix}"
