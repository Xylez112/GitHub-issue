"""Code Explorer — 搜索代码库，定位可疑代码。

Phase 0 占位版本：假数据，验证图能走通。
"""

from ..state import AnalysisState


def code_explorer_node(state: AnalysisState) -> dict:
    rounds = state.get("explore_rounds", 0) + 1
    return {
        "suspicious_snippets": [],
        "explored_enough": True,   # 占位：直接标记搜够了，防止无限循环
        "explore_rounds": rounds,
        "messages": state.get("messages", []) + ["[Explorer] Phase 0 placeholder"],
    }
