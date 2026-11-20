from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class NewsSource:
    id: str
    name: str
    url: str
    category: str


REAL_SOURCES = [
    NewsSource("openai", "OpenAI News", "https://openai.com/news/rss.xml", "产品动态"),
    NewsSource("huggingface", "Hugging Face Blog", "https://huggingface.co/blog/feed.xml", "开源模型与工具"),
    NewsSource("deepmind", "Google DeepMind Blog", "https://deepmind.google/blog/rss.xml", "AI 研究"),
    NewsSource("arxiv_ai", "arXiv cs.AI", "https://rss.arxiv.org/rss/cs.AI", "AI 研究"),
]

DEMO_SOURCES = [
    NewsSource("demo_coding", "演示样例：AI 编程工具", "demo://coding", "AI 编程工具"),
    NewsSource("demo_research", "演示样例：AI 研究", "demo://research", "AI 研究"),
    NewsSource("demo_broken", "演示样例：故障来源", "demo://broken", "故障演练"),
]


def source_list(demo_mode: bool) -> list[NewsSource]:
    return DEMO_SOURCES if demo_mode else REAL_SOURCES


def sources_as_dicts(demo_mode: bool) -> list[dict[str, str]]:
    return [asdict(source) for source in source_list(demo_mode)]
