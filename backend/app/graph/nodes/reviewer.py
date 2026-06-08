"""Reviewer — 审查修复方案，通过或驳回。

Phase 0 占位版本：直接全部通过。
"""

from ..state import AnalysisState


def reviewer_node(state: AnalysisState) -> dict:
    return {
        "review_votes": [
            {"fix_index": 0, "verdict": "approved", "feedback": "Phase 0 placeholder"}
        ],
        "all_approved": True,   # 占位：直接通过，让图走到 Reporter
        "messages": state.get("messages", []) + ["[Reviewer] Phase 0 placeholder"],
    }
