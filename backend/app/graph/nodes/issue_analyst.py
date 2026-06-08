"""Issue Analyst — 分析 GitHub Issue，提取结构化信息。

职责：
  1. 读 Issue 的 title + body
  2. 用 LLM 提取：错误类型 / 搜索关键词 / 结构化问题描述
  3. 写入 State，供后续 Agent（Code Explorer 等）使用

工具：无（这个 Agent 不需要调用外部工具，纯 LLM 分析）

设计原则（LLM + 代码的分工）：
  - LLM 负责"理解"：什么是错误类型、哪些词是关键术语
  - 代码负责"解析"：try/except + 默认值兜底，LLM 格式出错不崩溃
"""

import json
import re

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from ...core.config import settings, setup_logging
from ..state import AnalysisState

logger = setup_logging(__name__)

ANALYST_PROMPT = """You are an expert at analyzing GitHub Issues and bug reports.
Your job is to read an issue and extract structured information that helps
other agents search the codebase and write fixes.

## Output Format
Output ONLY a JSON object (no other text):

{
  "error_type": "Crash" | "LogicError" | "Performance" | "Configuration" | "Other",
  "keywords": ["3-5 specific terms to search in the codebase"],
  "error_context": "Structured summary of the problem in 2-4 sentences (use the original language of the issue)"
}

## Keyword Rules
- Include specific function/class/file names if mentioned (e.g. "create_user", "UserService")
- Include error message text (e.g. "KeyError", "AttributeError", "NoneType")
- Include relevant library/module names if the issue mentions them
- Do NOT include generic words like "error", "bug", "fix", "problem"
- Keep keywords in the original language/form from the issue

## Error Type Guide
- "Crash": Exceptions, tracebacks, segmentation faults
- "LogicError": Wrong results, incorrect behavior, unexpected output
- "Performance": Slow, memory leaks, high CPU
- "Configuration": Environment, dependencies, setup issues
- "Other": Anything that doesn't fit above
"""


def _parse_analyst_output(raw_text: str) -> dict:
    """确定性解析 LLM 输出 —— 永远不崩，最差返回默认值。

    为什么不用 Pydantic 验证？
    LLM 输出的 JSON 可能格式不完全正确（多一个逗号、少一个引号、
    多了一行解释文字）。Pydantic 会直接抛异常。
    这里用宽松正则 + try/except + 默认值兜底，
    保证系统在 LLM 输出异常时也能继续运行。
    """
    # 尝试提取 JSON 块（允许周围有非 JSON 文本）
    json_match = re.search(r"\{[\s\S]*\}", raw_text)
    if not json_match:
        logger.warning("Analyst: no JSON found in output, using defaults")
        return {
            "error_type": "Other",
            "keywords": [],
            "error_context": raw_text[:500],
        }

    try:
        data = json.loads(json_match.group(0))
    except json.JSONDecodeError as e:
        logger.warning("Analyst: JSON parse failed (%s), using defaults", e)
        return {
            "error_type": "Other",
            "keywords": [],
            "error_context": raw_text[:500],
        }

    return {
        "error_type": str(data.get("error_type", "Other")),
        "keywords": data.get("keywords", [])[:10],  # 最多 10 个关键词
        "error_context": str(data.get("error_context", raw_text[:500])),
    }


def issue_analyst_node(state: AnalysisState) -> dict:
    """分析 Issue，提取结构化信息写入 State。

    不调用任何工具——纯 LLM 推理就够了。
    后续的 Code Explorer 会消费这里产出的 keywords + error_context。
    """
    title = state.get("issue_title", "")
    context = state.get("error_context", "")  # 初始值来自 routes.py 的组装

    logger.info("Analyst: analyzing issue: %s", title[:80])

    # ChatOpenAI 会自动使用 OpenAI 兼容的 API 格式
    # DeepSeek 的 API 和 OpenAI 格式一致，所以 base_url 指向 DeepSeek
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=settings.deepseek_api_key,
        base_url="https://api.deepseek.com",
        temperature=0.1,  # 分析任务不需要创意，低温 = 确定性输出
    )

    messages = [
        SystemMessage(content=ANALYST_PROMPT),
        HumanMessage(content=f"## Issue Title\n{title}\n\n## Issue Body\n{context}"),
    ]

    response = llm.invoke(messages)
    parsed = _parse_analyst_output(response.content)

    result = {
        "error_type": parsed["error_type"],
        "keywords": parsed["keywords"],
        "error_context": parsed["error_context"],
    }

    logger.info(
        "Analyst: type=%s, keywords=%s",
        result["error_type"],
        result["keywords"],
    )

    # 追加日志——这是"审计追踪"，出问题时可以从 messages 里复盘
    msgs = state.get("messages", [])
    msgs.append(
        f"[Analyst] 错误类型: {result['error_type']} | "
        f"关键词: {', '.join(result['keywords'])}"
    )

    return {**result, "messages": msgs}
