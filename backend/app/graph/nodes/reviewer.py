"""Reviewer — 审查修复方案，通过或驳回。

设计要点：
  1. 每个 fix 单独审查（不是打总分）——针对性的反馈才有用
  2. 驳回必须带具体原因（feedback 字段）——供 Fix Crafter 参考
  3. 解析失败默认全部通过——宁可放过也不能让图卡死
  4. 和 Fix Crafter 用不同的 system prompt 人格——同一模型，不同角色
"""

import json
import re

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from ...core.config import settings, setup_logging
from ..state import AnalysisState

logger = setup_logging(__name__)

REVIEWER_SYSTEM = """You are a strict, adversarial code reviewer.
Your job is to find problems in fix suggestions BEFORE they reach production.
Be skeptical. Assume every fix has a hidden issue until proven otherwise.

## Review Criteria (check each one)
1. **Correctness**: Does the fix actually solve the reported bug?
2. **Safety**: Could this fix break existing functionality? Check edge cases.
3. **Completeness**: Are there other places that need the same fix?
4. **Style**: Does the fix match the project's existing code patterns?

## Output Format
```json
{
  "votes": [
    {
      "fix_index": 0,
      "verdict": "approved|rejected",
      "feedback": "Specific, actionable reason for the verdict"
    }
  ]
}
```

## Rules
- approve ONLY if the fix is demonstrably correct AND safe
- reject if anything looks wrong, incomplete, or risky
- be specific in feedback — say exactly what to change
- if you reject, tell the fixer what the correct approach should be
"""


def _parse_review_output(raw_text: str, fix_count: int) -> tuple[list[dict], bool]:
    """解析审查结果。

    兜底策略：如果 LLM 没返回有效 JSON，默认全部通过（避免图卡死）。
    这是一种防御性设计——"宁可放过不完美的修复，也不能没有结果"。
    """
    json_match = re.search(r"\{[\s\S]*\"votes\"[\s\S]*\}", raw_text)
    if not json_match:
        logger.warning("Reviewer: no JSON in output, auto-approving all")
        default = [
            {"fix_index": i, "verdict": "approved", "feedback": "Auto-approved (LLM parse error)"}
            for i in range(fix_count)
        ]
        return default, True

    try:
        data = json.loads(json_match.group(0))
        votes = data.get("votes", [])
    except json.JSONDecodeError:
        logger.warning("Reviewer: JSON parse failed, auto-approving all")
        default = [
            {"fix_index": i, "verdict": "approved", "feedback": "Auto-approved (parse error)"}
            for i in range(fix_count)
        ]
        return default, True

    all_ok = all(v.get("verdict") == "approved" for v in votes)
    return votes, all_ok


def reviewer_node(state: AnalysisState) -> dict:
    """审查每一个修复方案，决定通过还是驳回。"""
    fix_drafts = state.get("fix_drafts", [])
    error_context = state.get("error_context", "")
    error_type = state.get("error_type", "")

    if not fix_drafts:
        logger.warning("Reviewer: no fixes to review")
        msgs = state.get("messages", [])
        msgs.append("[Reviewer] 没有修复方案需要审查")
        return {"all_approved": True, "messages": msgs, "review_votes": []}

    logger.info("Reviewer: reviewing %d fixes", len(fix_drafts))

    # 构建审查上下文——每个 fix 都会展示给 Reviewer
    fixes_text = []
    for i, f in enumerate(fix_drafts):
        fixes_text.append(
            f"### Fix #{i}\n"
            f"File: `{f.get('file_path', '?')}`\n"
            f"Function: `{f.get('name', '?')}`\n"
            f"Crafters rationale: {f.get('rationale', 'none')}\n"
            f"**Original Code:**\n```python\n{f.get('original_code', 'N/A')[:1500]}\n```\n"
            f"**Fixed Code:**\n```python\n{f.get('fixed_code', 'N/A')[:1500]}\n```"
        )

    user_prompt = f"""## Original Bug
Error Type: {error_type}
{error_context}

## Fix Proposals
{chr(10).join(fixes_text)}

Review each fix carefully. Be strict — reject anything that could cause problems."""

    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=settings.deepseek_api_key,
        base_url="https://api.deepseek.com",
        temperature=0.1,
    )

    response = llm.invoke([
        SystemMessage(content=REVIEWER_SYSTEM),
        HumanMessage(content=user_prompt),
    ])

    votes, all_approved = _parse_review_output(response.content, len(fix_drafts))

    approved_count = sum(1 for v in votes if v.get("verdict") == "approved")
    rejected_count = len(votes) - approved_count
    logger.info("Reviewer: %d approved, %d rejected", approved_count, rejected_count)

    msgs = state.get("messages", [])
    msgs.append(f"[Reviewer] {approved_count} 通过, {rejected_count} 驳回")

    return {
        "review_votes": votes,
        "all_approved": all_approved,
        "messages": msgs,
    }
