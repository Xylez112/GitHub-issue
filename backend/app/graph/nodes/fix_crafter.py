"""Fix Crafter — 基于可疑代码生成修复方案。

Phase 0 占位版本。
"""

from ..state import AnalysisState


def fix_crafter_node(state: AnalysisState) -> dict:
    return {
        "fix_drafts": [{
            "file_path": "placeholder.py",
            "name": "placeholder_func",
            "line_start": 1,
            "line_end": 5,
            "original_code": "# placeholder",
            "fixed_code": "# fixed placeholder",
            "rationale": "Phase 0 placeholder",
        }],
        "messages": state.get("messages", []) + ["[Crafter] Phase 0 placeholder"],
    }
