import re
from . import embedder
from .github import IssueData
from ..models.schemas import CodeSnippet


# ============================================================
# 1. 清洗层 —— 把 Issue body 里的噪音去掉
# ============================================================

# 匹配各种客套话开头，这些跟代码语义完全无关
_SOCIAL_PATTERNS = [
    r"^(Hi|Hello|Hey|Dear)\b.*$",
    r"^(Thanks|Thank you|Thanks for)\b.*$",
    r"^(First of all|First off)\b.*$",
    r"^(I (just |)wanted to)\b.*$",
    r"^(Great|Awesome|Nice) (library|project|work|tool)\b.*$",
    r"^(Sorry|Apologies)\b.*$",
]


def _clean_text(text: str) -> str:
    """去掉社交废话、markdown 标记、多余空白。"""
    # 去掉客套话行
    for pat in _SOCIAL_PATTERNS:
        text = re.sub(pat, "", text, flags=re.MULTILINE | re.IGNORECASE)

    # 去掉 markdown 标题标记 (# ## ### ...)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # 去掉粗体/斜体标记
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    # 去掉行内代码标记 `...`
    text = re.sub(r"`{1,2}(.+?)`{1,2}", r"\1", text)
    # 去掉横线
    text = re.sub(r"^-{3,}$", "", text, flags=re.MULTILINE)
    # 去掉 checkbox
    text = re.sub(r"^[-*]\s*\[[ x]\]", "", text, flags=re.MULTILINE)

    # 合并多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()


def _remove_environment_sections(text: str) -> str:
    """去掉环境信息区块（OS/版本号/pip list 等），这些是代码检索的噪音。"""
    # 去掉整个 Environment / System Info 章节
    text = re.sub(
        r"#{1,6}\s*(Environment|System Info|Your Environment|Setup|Installation|Dependencies).*?(?=\n#{1,6}|\Z)",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # 去掉 pip freeze / conda list 的输出行 (package==version)
    text = re.sub(r"^[a-zA-Z0-9_.-]+==[\d.]+.*$", "", text, flags=re.MULTILINE)
    # 去掉 OS / Python version 这种单行
    text = re.sub(
        r"^(OS|Operating System|Python Version|Node Version|Browser):.*$",
        "",
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )

    return text


# ============================================================
# 2. 提取层 —— 从 body 里抓出高信号内容
# ============================================================


def _extract_code_blocks(text: str) -> list[str]:
    """提取 markdown 围栏代码块 (```...```)，通常包含 traceback 或复现代码。"""
    pattern = r"```(?:\w*\n)?(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    return [m.strip() for m in matches if len(m.strip()) > 20]


def _extract_tracebacks(text: str) -> list[str]:
    """提取 Python traceback 行。"""
    lines: list[str] = []
    in_tb = False
    for line in text.split("\n"):
        stripped = line.strip()
        if "Traceback (most recent call last)" in stripped:
            in_tb = True
        if in_tb:
            lines.append(stripped)
            # traceback 最后一行是实际的 Error 类型 + 消息
            if stripped and not stripped.startswith("File ") and "Error" in stripped:
                break
    return lines


# ============================================================
# 3. 查询构造 —— 拼接清洗后的文本
# ============================================================


def _build_queries(issue: IssueData) -> list[str]:
    """从 Issue 构造 1~2 个干净的查询字符串。"""
    title = issue.title or ""
    body = issue.body or ""

    if not body:
        return [title]

    # 先去环境噪音
    body = _remove_environment_sections(body)

    # 提取高信号片段
    code_blocks = _extract_code_blocks(body)
    tracebacks = _extract_tracebacks(body)

    # 清洗剩余正文
    cleaned_body = _clean_text(body)

    queries = []

    # 查询1: title + 清洗后的正文（前800字符）
    body_short = cleaned_body[:800].strip()
    if body_short:
        queries.append(f"{title}\n{body_short}")
    else:
        queries.append(title)

    # 查询2: title + 提取出的代码/traceback（如果存在）
    signal_parts: list[str] = []
    for tb in tracebacks:
        signal_parts.append(tb)
    for cb in code_blocks:
        signal_parts.append(cb)

    if signal_parts:
        queries.append(f"{title}\n" + "\n".join(signal_parts))

    return queries


# ============================================================
# 4. 检索入口 —— 多查询 → 合并 → 去重 → 排序
# ============================================================


def retrieve(
    issue: IssueData, collection_name: str, top_k: int = 10
) -> list[tuple[CodeSnippet, float]]:
    """用清洗后的多查询检索相关代码片段，去重后返回 top_k。"""
    queries = _build_queries(issue)

    # key = "file_path:name"，用于去重
    seen: dict[str, tuple[CodeSnippet, float]] = {}

    # 每个查询拿 top_k 的一半，保证结果多样性
    per_query = max(1, top_k // len(queries))
    for query in queries:
        results = embedder.search_snippets(query, collection_name, top_k=per_query)
        for snippet, score in results:
            key = f"{snippet.file_path}:{snippet.name}"
            # 同一个片段命中多次 → 取最高分
            if key not in seen or score > seen[key][1]:
                seen[key] = (snippet, score)

    # 按相似度降序，截断到 top_k
    sorted_results = sorted(seen.values(), key=lambda x: x[1], reverse=True)
    return sorted_results[:top_k]
