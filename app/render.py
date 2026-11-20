from __future__ import annotations


def brief_markdown(content: dict) -> str:
    lines = ["# 每日 AI 新闻简报", ""]
    if content.get("demo_sample"):
        lines.extend(["> 演示样例 / 离线测试替身运行，非真实新闻或真实 LLM 结果。", ""])
    items = content.get("items", [])
    if not items:
        lines.extend(["## 今日没有匹配的新闻", "", content.get("note", "")])
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
    suffix = "无匹配新闻" if not content.get("items") else f"{len(content['items'])} 条精选"
    return f"{prefix}每日 AI 新闻简报 {brief_date} · {suffix}"
