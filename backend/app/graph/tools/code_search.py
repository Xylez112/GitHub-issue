"""search_code 工具 —— 封装现有的 retriever 为 LLM 可调用的 LangChain Tool。

设计要点：
  - 返回格式化文本（不是对象）——LLM 的上下文是纯文本
  - 结果数量有上限（top_k ≤ 10）——防止塞爆 LLM 上下文窗口
  - 单段代码截断到 1500 字符——大函数不占满整个 prompt

和 MVP 里 retriever.search_snippets() 的关系：
  - retriever 是底层能力（谁都可以调）
  - search_code 是给 LLM 用的适配层（加了格式化、截断、错误处理）
  - LLM 不知道 retriever 存在，它只知道"有个 search_code 工具可以用"
"""

from langchain_core.tools import tool

from ...services.embedder import search_snippets as embedding_search


@tool
def search_code(query: str, collection_name: str, top_k: int = 5) -> str:
    """Search the entire codebase for functions, classes, and methods relevant to the query.

    Use this tool when:
    - You need to find which files contain code related to a bug
    - You want to locate a specific function or class mentioned in the issue
    - You need to understand what code might be causing the problem

    Args:
        query: Natural language or code snippet to search for
               (e.g. "user creation function" or "KeyError: user_id")
        collection_name: ChromaDB collection name (provided by the system)
        top_k: Number of results (1-10, default 5)

    Returns:
        Formatted string listing the most relevant code snippets with
        file paths, line numbers, and code
    """
    try:
        results = embedding_search(query, collection_name, top_k=min(top_k, 10))
    except Exception as e:
        return f"Search failed: {e}"

    if not results:
        return "No matching code found. Try different keywords or a broader query."

    output_parts = []
    for i, (snippet, score) in enumerate(results, 1):
        # 截断长代码，防止一个巨大的函数占满 LLM 上下文
        code = snippet.code[:1500]
        if len(snippet.code) > 1500:
            code += "\n# ... (truncated, use read_file to see full code)"

        output_parts.append(
            f"### Result {i} (score: {score:.3f})\n"
            f"File: `{snippet.file_path}`\n"
            f"Name: `{snippet.name}` ({snippet.kind})\n"
            f"Lines: {snippet.line_start}-{snippet.line_end}\n"
            f"```python\n{code}\n```"
        )

    return "\n\n".join(output_parts)
