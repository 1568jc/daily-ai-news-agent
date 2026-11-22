from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class NewsSource:
    id: str
    name: str
    url: str
    category: str


REAL_SOURCES = [
    NewsSource("openai", "OpenAI News", "https://openai.com/news/rss.xml", "官方产品"),
    NewsSource("huggingface", "Hugging Face Blog", "https://huggingface.co/blog/feed.xml", "开源模型与工具"),
    NewsSource("deepmind", "Google DeepMind Blog", "https://deepmind.google/blog/rss.xml", "官方研究"),
    NewsSource("google_ai", "Google AI Blog", "https://blog.google/technology/ai/rss/", "官方产品与研究"),
    NewsSource("microsoft_research", "Microsoft Research Blog", "https://www.microsoft.com/en-us/research/feed/", "官方研究"),
    NewsSource("aws_ml", "AWS Machine Learning Blog", "https://aws.amazon.com/blogs/machine-learning/feed/", "云计算与机器学习工程"),
    NewsSource("github_ai", "GitHub AI & ML Blog", "https://github.blog/ai-and-ml/feed/", "AI 编程与工程实践"),
    NewsSource("techcrunch_ai", "TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", "行业动态与产品新闻"),
    NewsSource("mit_ai", "MIT Technology Review AI", "https://www.technologyreview.com/topic/artificial-intelligence/feed/", "行业趋势与技术解读"),
    NewsSource("arxiv_ai", "arXiv cs.AI", "https://rss.arxiv.org/rss/cs.AI", "人工智能论文"),
    NewsSource("arxiv_lg", "arXiv cs.LG", "https://rss.arxiv.org/rss/cs.LG", "机器学习论文"),
    NewsSource("arxiv_cl", "arXiv cs.CL", "https://rss.arxiv.org/rss/cs.CL", "自然语言处理论文"),
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
