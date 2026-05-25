import json
import re

from openai import AsyncOpenAI

from ..core.config import settings
from ..models.schemas import CodeSnippet, FixSuggestion
from .github import IssueData

_client = AsyncOpenAI(
    api_key=settings.deepseek_api_key,
    base_url="https://api.deepseek.com",
)

SYSTEM_PROMPT = """You are an expert code reviewer and debugger. Given a GitHub Issue and relevant code snippets from the repository, your task is to:

1. Identify which code snippets are most likely related to the issue
2. Explain why each snippet is relevant
3. Provide concrete fix suggestions with code changes

Follow these rules:
- Only flag snippets that have a clear, explainable connection to the issue
- If no snippet is clearly related, say so honestly rather than forcing a connection
- Suggest specific code changes, not vague advice
- Be conservative: prefer minimal, safe fixes over large rewrites
- Consider edge cases and potential side effects of your suggestions

Output your analysis as a JSON object with the following structure:
{
  "analysis_summary": "Brief overview of your findings",
  "suggestions": [
    {
      "file_path": "path/to/file.py",
      "name": "function_or_class_name",
      "line_start": 10,
      "line_end": 25,
      "issue_summary": "What part of the issue this code relates to",
      "suggested_fix": "Detailed fix description with code changes",
      "confidence": "high|medium|low"
    }
  ]
}
"""


def _build_user_message(
    issue: IssueData,
    snippets: list[tuple[CodeSnippet, float]],
) -> str:
    lines = [
        f"## GitHub Issue\n",
        f"**Title**: {issue.title}\n",
        f"**Body**:\n{issue.body}\n",
        f"## Retrieved Code Snippets (ranked by relevance)\n",
    ]

    for i, (snippet, score) in enumerate(snippets, 1):
        lines.append(
            f"### Snippet {i} (score: {score:.3f})\n"
            f"**File**: `{snippet.file_path}`\n"
            f"**Name**: `{snippet.name}` ({snippet.kind})\n"
            f"**Lines**: {snippet.line_start}-{snippet.line_end}\n"
            f"```python\n{snippet.code}\n```\n"
        )

    return "\n".join(lines)


def _parse_response(text: str) -> tuple[str, list[FixSuggestion]]:
    json_match = re.search(r"\{[\s\S]*\}", text)
    if not json_match:
        return text, []

    try:
        data = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return text, []

    summary = data.get("analysis_summary", "")
    suggestions = [
        FixSuggestion(
            file_path=s.get("file_path", ""),
            name=s.get("name", ""),
            line_start=s.get("line_start", 0),
            line_end=s.get("line_end", 0),
            issue_summary=s.get("issue_summary", ""),
            suggested_fix=s.get("suggested_fix", ""),
            confidence=s.get("confidence", "medium"),
        )
        for s in data.get("suggestions", [])
    ]

    return summary, suggestions


async def analyze(
    issue: IssueData,
    snippets: list[tuple[CodeSnippet, float]],
) -> tuple[str, str, list[FixSuggestion]]:
    user_message = _build_user_message(issue, snippets)

    resp = await _client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=4096,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )

    raw_text = resp.choices[0].message.content
    summary, suggestions = _parse_response(raw_text)
    return raw_text, summary, suggestions
