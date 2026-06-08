"""StateGraph 构建器 —— 把 5 个节点 + 条件边组装成一张可执行图。

这张图做什么：
  1. 从 issue_analyst 开始
  2. 流向 code_explorer（搜索代码）
  3. Explorer 搜够了 → fix_crafter；搜不到 → 回到 analyst 重新分析
  4. Fix Crafter 出方案后 → reviewer 审查
  5. Reviewer 通过 → reporter 生成报告；驳回 → 回到 fix_crafter 重改
  6. Reporter 完成 → END（图终止）

防无限循环：
  - explore_rounds > 5 时强制回到 issue_analyst
  - LangGraph compile() 默认 recursion_limit=25，全图超过 25 步强制终止

使用方式：
    from .builder import build_graph
    graph = build_graph()
    result = await graph.ainvoke(initial_state)
"""

from langgraph.graph import StateGraph, END

from .state import AnalysisState
from .nodes import (
    issue_analyst_node,
    code_explorer_node,
    fix_crafter_node,
    reviewer_node,
    reporter_node,
)


def route_after_explore(state: AnalysisState) -> str:
    """Code Explorer 完成一轮搜索后，决定下一步去哪。

    三种情况：
    1. explored_enough = True → 搜够了，去 fix_crafter
    2. explore_rounds > 5 → 搜了 5 轮都没找到，可能是关键词不对，回去找 Analyst
    3. 否则 → 继续本轮搜索（再搜一轮）

    这个函数叫 "router" — 它的返回值必须是图里注册过的节点名。
    """
    if state.get("explored_enough", False):
        return "fix_crafter"
    if state.get("explore_rounds", 0) > 5:
        return "issue_analyst"
    return "code_explorer"


def route_after_review(state: AnalysisState) -> str:
    """Reviewer 审查完后，决定下一步去哪。

    两种结果：
    1. all_approved = True → 全部通过，去 reporter 出报告
    2. 否则 → 打回 fix_crafter 重改（带着 reviewer 的 feedback）

    注意：这里没有"重审次数"限制——reviewer → crafter → reviewer 的循环
    由 LangGraph 的 recursion_limit 兜底（默认 25 步）。
    """
    if state.get("all_approved", False):
        return "reporter"
    return "fix_crafter"


def build_graph() -> StateGraph:
    """构建并返回编译好的 Agent 图。

    调用方（routes.py）这样用：
        graph = build_graph()
        result = await graph.ainvoke(initial_state)

    节点注册顺序不重要——边决定了执行顺序。
    但节点名必须在 add_conditional_edges 的映射表里出现。
    """
    graph = StateGraph(AnalysisState)

    # 注册 5 个节点（名字是路由键，必须和 conditional_edges 的返回值一致）
    graph.add_node("issue_analyst", issue_analyst_node)
    graph.add_node("code_explorer", code_explorer_node)
    graph.add_node("fix_crafter", fix_crafter_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("reporter", reporter_node)

    # 入口：从 Issue Analyst 开始
    graph.set_entry_point("issue_analyst")

    # Analyst → Explorer（固定边：分析完必定去搜索）
    graph.add_edge("issue_analyst", "code_explorer")

    # Explorer → 条件路由
    # router 返回 "fix_crafter" / "issue_analyst" / "code_explorer" 之一
    # 第三个参数是"映射表"：router 返回值 → 目标节点名
    graph.add_conditional_edges(
        "code_explorer",
        route_after_explore,
        {
            "fix_crafter": "fix_crafter",
            "issue_analyst": "issue_analyst",
            "code_explorer": "code_explorer",
        },
    )

    # Crafter → Reviewer（固定边：出完方案必定去审查）
    graph.add_edge("fix_crafter", "reviewer")

    # Reviewer → 条件路由（通过 → Reporter，驳回 → Crafter）
    graph.add_conditional_edges(
        "reviewer",
        route_after_review,
        {
            "reporter": "reporter",
            "fix_crafter": "fix_crafter",
        },
    )

    # Reporter → END（图终止）
    graph.add_edge("reporter", END)

    # 编译成可执行应用
    return graph.compile()
