"""共享 State —— 所有 Agent 节点读写的"黑板"。

LangGraph 的 State 本质是一个 TypedDict。每个节点函数接受 state，
返回一个 dict 表示"要更新的字段"。框架自动合并——返回什么就更新什么，
不返回的字段保持不变。这让每个节点只看自己关心的部分。

设计原则：
- State 是"只增不减"的日志簿（messages 只往后面加，不删除历史）
- 每个字段有明确的"谁产出 / 谁消费"——避免混乱
- total=False 意味着所有字段可缺省，初始 State 只填入已知输入
"""

from typing import TypedDict


class AnalysisState(TypedDict, total=False):
    """total=False 意味着所有字段都是可选的（Optional）。

    原因：初始 State 只填充输入字段（issue_url, repo_url），
    后续字段由各节点逐步填充。如果 total=True，
    StateGraph 启动时会因为字段缺失报错。
    """

    # ── 输入（API 传入）──
    issue_url: str
    repo_url: str
    repo_path: str          # clone 后的本地路径，由 routes.py 预先 clone

    # ── Issue Analyst 产出 ──
    issue_title: str        # Issue 标题（从 API 传入）
    error_type: str         # "Crash" | "LogicError" | "Performance" | ...
    keywords: list[str]     # 搜索关键词（给 Code Explorer 用的）
    error_context: str      # 结构化问题描述（Markdown 格式）

    # ── Code Explorer 产出 ──
    suspicious_snippets: list[dict]
    # 每个 dict: {file_path, name, line_start, line_end, code, kind, reason, relevance_score}
    explored_enough: bool   # True = 搜够了，路由去 Fix Crafter
    explore_rounds: int     # 搜了几轮，防无限循环

    # ── Fix Crafter 产出 ──
    fix_drafts: list[dict]
    # 每个 dict: {file_path, name, line_start, line_end, original_code, fixed_code, rationale}

    # ── Reviewer 产出 ──
    review_votes: list[dict]
    # 每个 dict: {fix_index: int, verdict: "approved"|"rejected", feedback: str}
    all_approved: bool

    # ── Reporter 产出 ──
    final_report: str       # Markdown 格式的完整分析报告

    # ── 全局（调试 + 审计）──
    messages: list[str]     # 每个节点的关键日志（"Analyst 提取了 3 个关键词: ..."）
    errors: list[str]       # 运行期错误（"Explorer: 工具 search_code 超时"）
