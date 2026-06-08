"""Reporter — 汇总所有 Agent 产出，生成 Markdown 报告。

Phase 0 占位版本。
"""

from ..state import AnalysisState


def reporter_node(state: AnalysisState) -> dict:
    report = f"""# Analysis Report (Phase 0 Placeholder)

## Issue
{state.get('error_context', 'N/A')}

## Suspicious Code
{len(state.get('suspicious_snippets', []))} snippets found.

## Fix Suggestions
{len(state.get('fix_drafts', []))} fixes drafted.

## Review
All approved: {state.get('all_approved', False)}
"""
    return {
        "final_report": report,
        "messages": state.get("messages", []) + ["[Reporter] Phase 0 placeholder"],
    }
