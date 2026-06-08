"""Issue Analyst — 分析 GitHub Issue，提取结构化信息。

Phase 0 占位版本：直接写入假数据，用于验证图能跑通。
后续 Phase 1 会替换为真正的 LLM 分析逻辑。
"""

from ..state import AnalysisState


def issue_analyst_node(state: AnalysisState) -> dict:
    return {
        "error_type": "Crash",
        "keywords": ["placeholder", "test"],
        "error_context": "Phase 0 placeholder — will be replaced in Phase 1",
        "messages": ["[Analyst] Phase 0 placeholder ran successfully"],
    }
