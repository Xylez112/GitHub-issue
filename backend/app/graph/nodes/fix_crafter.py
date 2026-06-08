"""Fix Crafter — 基于可疑代码生成具体修复方案。

职责单一：拿 Code Explorer 找到的代码 + Issue 描述 → 写出修复 diff。

不需要工具（纯推理），不需要循环（输入确定，一次搞定）。

为什么把"找代码"和"写修复"拆成两个 Agent？
  关注点分离：
  - Explorer 负责"哪里有问题"（搜索、读文件、追踪调用链）
  - Crafter 负责"怎么修"（理解代码逻辑，写正确的修复）
  合并成一个 Agent 会让 prompt 太长，LLM 容易"粗看就写"而不是仔细排查。
"""

import json
import re

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from ...core.config import settings, setup_logging
from ..state import AnalysisState

logger = setup_logging(__name__)

CRAFTER_SYSTEM = """You are an expert code fixer. Given a bug description and suspicious code,
write concrete, safe fixes.

## Rules
- Be minimal: fix only what's broken, don't refactor unrelated code
- Be safe: consider edge cases (None, empty list, invalid input, race conditions)
- Be specific: show the EXACT code change (original vs fixed)
- Be honest: if you can't determine the fix from the available code, say so

## Output Format
```json
{
  "fixes": [
    {
      "file_path": "path/to/file.py",
      "name": "function_name",
      "line_start": 10,
      "line_end": 25,
      "original_code": "the current buggy code",
      "fixed_code": "the corrected code",
      "rationale": "Why this fix addresses the issue"
    }
  ]
}
```

If no code block is clearly related to the bug, return an empty fixes list.
"""


def _parse_crafter_output(raw_text: str) -> list[dict]:
    """解析 LLM 输出的修复方案列表。兜底：解析失败返回空列表。"""
    json_match = re.search(r"\{[\s\S]*\"fixes\"[\s\S]*\}", raw_text)
    if not json_match:
        logger.warning("Crafter: no fixes JSON found in output")
        return []

    try:
        data = json.loads(json_match.group(0))
        return data.get("fixes", [])
    except json.JSONDecodeError:
        logger.warning("Crafter: JSON parse failed")
        return []


def fix_crafter_node(state: AnalysisState) -> dict:
    """基于可疑代码生成修复方案。"""
    error_context = state.get("error_context", "")
    error_type = state.get("error_type", "")
    suspicious = state.get("suspicious_snippets", [])

    if not suspicious:
        logger.warning("Crafter: no suspicious snippets to work with")
        msgs = state.get("messages", [])
        msgs.append("[Crafter] 没有可疑代码，无法生成修复方案")
        return {"fix_drafts": [], "messages": msgs}

    logger.info("Crafter: drafting fixes for %d suspicious snippets", len(suspicious))

    # 构建代码上下文——给 LLM 展示每段可疑代码
    code_context_parts = []
    for i, s in enumerate(suspicious):
        code_block = s.get("code", "")
        if not code_block or len(code_block) < 10:
            code_block = (
                f"(完整代码未加载——请用 read_file 读取 "
                f"`{s.get('file_path', '?')}` 查看)"
            )
        code_context_parts.append(
            f"### 可疑代码 #{i + 1}\n"
            f"文件: `{s.get('file_path', '?')}`\n"
            f"函数/类: `{s.get('name', '?')}`\n"
            f"相关原因: {s.get('reason', '未说明')}\n"
            f"```python\n{code_block[:2000]}\n```"
        )

    user_prompt = f"""## Bug 描述
错误类型: {error_type}
{error_context}

## 可疑代码
{chr(10).join(code_context_parts)}

对每段与 Bug 明显相关的可疑代码，写出修复方案。
如果某段代码看起来不相关，跳过它。"""

    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=settings.deepseek_api_key,
        base_url="https://api.deepseek.com",
        temperature=0.1,
    )

    response = llm.invoke([
        SystemMessage(content=CRAFTER_SYSTEM),
        HumanMessage(content=user_prompt),
    ])

    fixes = _parse_crafter_output(response.content)
    logger.info("Crafter: generated %d fixes", len(fixes))

    # 标准化输出格式——确保所有必需字段存在
    fix_drafts = []
    for f in fixes:
        fix_drafts.append({
            "file_path": f.get("file_path", ""),
            "name": f.get("name", ""),
            "line_start": f.get("line_start", 0),
            "line_end": f.get("line_end", 0),
            "original_code": f.get("original_code", ""),
            "fixed_code": f.get("fixed_code", ""),
            "rationale": f.get("rationale", ""),
        })

    msgs = state.get("messages", [])
    msgs.append(f"[Crafter] 生成了 {len(fix_drafts)} 个修复方案")

    return {"fix_drafts": fix_drafts, "messages": msgs}
