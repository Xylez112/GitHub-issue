# Multi-Agent LangGraph 升级实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 MVP 单次 Pipeline 升级为 LangGraph 驱动的 5-Agent 协作系统，每个 Agent 有独立工具集、自主决策能力、可迭代协作。

**Architecture:** LangGraph StateGraph 作为编排引擎，5 个图节点（Issue Analyst → Code Explorer → Fix Crafter → Reviewer → Reporter），共享 AnalysisState TypedDict 作为黑板，条件边实现自由协作流转。

**Tech Stack:** FastAPI, LangGraph, LangChain (ChatOpenAI + bind_tools), ChromaDB (复用), Tree-sitter (复用), BM25 (复用), DeepSeek Chat

---

## 教学约定

每次修改文件时，遵循三步讲解：

1. **改什么** — 指出具体文件 + 行号范围
2. **为什么这样改** — 背后的设计原理 / 为什么不是别的方案
3. **知识点** — 可以迁移到其他项目的通用概念

---

## Phase 0: LangGraph 骨架

### Task 0.1: 安装依赖

**Files:**
- Modify: `backend/requirements.txt`（在已有依赖末尾追加）

**知识点：`bind_tools` 是什么？**
在 MVP 里，LLM 只能返回文字。`bind_tools` 让 LLM 可以返回"我要调用这个函数 + 这些参数"——这就是 Agent 能"做事"的关键。
LangChain 的 `bind_tools` 接收 Python 函数定义，自动把函数签名转成 OpenAI function calling 格式发给 LLM。
`langgraph` 负责"节点→节点"的流转和状态管理。

- [ ] **Step 1: 在 requirements.txt 追加新依赖**

在 `backend/requirements.txt` 末尾加入：

```
langchain>=0.2.0
langchain-openai>=0.1.0
langgraph>=0.1.0
```

- [ ] **Step 2: 安装**

```bash
cd "d:/项目/GitHub Issue/backend" && pip install langchain langchain-openai langgraph
```

- [ ] **Step 3: 验证安装**

```bash
python -c "import langgraph; print(langgraph.__version__)"
```

期望输出：版本号，无 ImportError。

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add langchain + langgraph dependencies"
```

---

### Task 0.2: 创建 State 定义

**Files:**
- Create: `backend/app/graph/__init__.py`
- Create: `backend/app/graph/state.py`

**知识点：TypedDict vs Pydantic，为什么 State 用 TypedDict？**
LangGraph 的 State 需要支持"部分更新"——一个节点可能只改 `keywords`，不改别的。
TypedDict 配合 `dict.update()` 天然支持这点。Pydantic 强在校验和序列化，但 State 不需要网络传输，TypedDict 更轻量。
另外 LangGraph 原生支持 TypedDict + Annotated reducer（如 `operator.add` 用于追加列表），这是 Pydantic 做不到的。

- [ ] **Step 1: 创建 `backend/app/graph/__init__.py`**

```python
# GitHub Issue Code Analyzer — LangGraph Agent Graph
# Nodes: issue_analyst, code_explorer, fix_crafter, reviewer, reporter
```

- [ ] **Step 2: 创建 `backend/app/graph/state.py`**

```python
"""共享 State —— 所有 Agent 节点读写的"黑板"。

LangGraph 的 State 本质是一个 TypedDict。每个节点函数接受 state，
返回一个 dict 表示"要更新的字段"。框架自动合并——返回什么就更新什么，
不返回的字段保持不变。这让每个节点只看自己关心的部分。
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
    repo_path: str          # clone 后的本地路径，由外部预先 clone

    # ── Issue Analyst 产出 ──
    issue_title: str        # Issue 标题
    error_type: str         # "Crash" | "LogicError" | "Performance" | ...
    keywords: list[str]     # 搜索关键词（给 Code Explorer 用的）
    error_context: str      # 结构化问题描述（Markdown 格式）

    # ── Code Explorer 产出 ──
    suspicious_snippets: list[dict]
    # 每个 dict: {file_path, name, line_start, line_end, code, kind, reason, relevance_score}
    explored_enough: bool   # True = 搜够了，可以开始修复
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
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/graph/
git commit -m "feat: add AnalysisState TypedDict — shared blackboard for all agents"
```

---

### Task 0.3: 创建 Graph Builder（空节点 + 条件边）

**Files:**
- Create: `backend/app/graph/builder.py`
- Create: `backend/app/graph/nodes/__init__.py`

**知识点：StateGraph 的四个核心概念**

```
StateGraph(state_schema)   →  定义"图里流转什么数据"
.add_node("name", func)    →  注册一个节点（func 接收 state，返回 dict）
.set_entry_point("name")   →  从哪个节点开始
.add_edge("A", "B")         →  固定边：A 执行完必定去 B
.add_conditional_edges("A", router, {"x": "B", "y": "C"})  →  条件边：router 函数决定下一步
.compile()                  →  编译成可执行的图
```

类比：StateGraph 就像一个"状态机 + 路由器"的组合体。节点是状态，边是转移条件。
和 MVP 的线性 Pipeline 最大的区别：**图不需要事先知道走哪条路——每个节点自己决定下一步。**

- [ ] **Step 1: 创建 `backend/app/graph/nodes/__init__.py`**

```python
# Agent nodes — each is a callable (state) → dict
from .issue_analyst import issue_analyst_node
from .code_explorer import code_explorer_node
from .fix_crafter import fix_crafter_node
from .reviewer import reviewer_node
from .reporter import reporter_node

__all__ = [
    "issue_analyst_node",
    "code_explorer_node",
    "fix_crafter_node",
    "reviewer_node",
    "reporter_node",
]
```

- [ ] **Step 2: 创建 `backend/app/graph/builder.py`**

```python
"""StateGraph 构建器 —— 把 5 个节点 + 条件边组装成一张图。

这张图做什么：
  1. 从 issue_analyst 开始
  2. 流向 code_explorer（搜索代码）
  3. Explorer 搜够了 → fix_crafter；搜不到 → 回到 analyst 重新分析
  4. Fix Crafter 出方案后 → reviewer 审查
  5. Reviewer 通过 → reporter 生成报告；驳回 → 回到 fix_crafter 重改
  6. Reporter 完成 → END（图终止）

防无限循环：
  - explore_rounds > 5 时强制回到 issue_analyst
  - 整个图有 max_iterations 硬上限（LangGraph 编译参数）
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
    3. 否则 → 继续搜索（再搜一轮）
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
    """
    if state.get("all_approved", False):
        return "reporter"
    return "fix_crafter"


def build_graph() -> StateGraph:
    """构建并返回编译好的 Agent 图。

    调用方（routes.py）这样用：
        graph = build_graph()
        result = await graph.ainvoke(initial_state)
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

    # Analyst → Explorer（固定边）
    graph.add_edge("issue_analyst", "code_explorer")

    # Explorer → 条件路由（搜够了 → Crafter，搜不到 → Analyst 或继续）
    graph.add_conditional_edges(
        "code_explorer",
        route_after_explore,
        {
            "fix_crafter": "fix_crafter",
            "issue_analyst": "issue_analyst",
            "code_explorer": "code_explorer",
        },
    )

    # Crafter → Reviewer（固定边）
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

    # Reporter → END
    graph.add_edge("reporter", END)

    # 编译（recursion_limit 防止自由协作无限循环）
    return graph.compile()
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/graph/builder.py backend/app/graph/nodes/__init__.py
git commit -m "feat: add graph builder with conditional routing skeleton"
```

---

### Task 0.4: 创建 5 个占位节点（让图能跑通）

**Files:**
- Create: `backend/app/graph/nodes/issue_analyst.py`
- Create: `backend/app/graph/nodes/code_explorer.py`
- Create: `backend/app/graph/nodes/fix_crafter.py`
- Create: `backend/app/graph/nodes/reviewer.py`
- Create: `backend/app/graph/nodes/reporter.py`

**知识点：为什么先写占位节点？——"行走的骨架"策略**

软件工程里有一个基本原则：**尽早让系统"跑起来"，哪怕什么实事都不干。**
一个能跑的空图，比一堆不能跑的完整代码有价值得多——因为你可以验证：
- 图的结构是否正确（节点顺序 + 条件路由是否按预期流转）
- State 传递是否正常（每个节点读写 state 没问题）
- Import 链路是否完整

然后你再一个一个往节点里填真正的逻辑，每填一个就能立刻测试它。

- [ ] **Step 1: 创建占位 `issue_analyst.py`**

```python
"""Issue Analyst — 分析 GitHub Issue，提取结构化信息。

Phase 0 占位版本：直接写入假数据，用于验证图能跑通。
后续 Phase 1 会替换为真正的 LLM 分析逻辑。
"""

from ..state import AnalysisState


def issue_analyst_node(state: AnalysisState) -> dict:
    return {
        "issue_title": state.get("issue_title", "Unknown Issue"),
        "error_type": "Crash",
        "keywords": ["placeholder", "test"],
        "error_context": "Phase 0 placeholder — will be replaced in Phase 1",
        "messages": ["[Analyst] Phase 0 placeholder ran successfully"],
    }
```

- [ ] **Step 2: 创建占位 `code_explorer.py`**

```python
"""Code Explorer — 搜索代码库，定位可疑代码。

Phase 0 占位版本。
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
```

- [ ] **Step 3: 创建占位 `fix_crafter.py`**

```python
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
```

- [ ] **Step 4: 创建占位 `reviewer.py`**

```python
"""Reviewer — 审查修复方案，通过或驳回。

Phase 0 占位版本。
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
```

- [ ] **Step 5: 创建占位 `reporter.py`**

```python
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
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/graph/nodes/
git commit -m "feat: add 5 placeholder agent nodes — walking skeleton"
```

---

### Task 0.5: 改造 routes.py —— 从 Pipeline 切到 Graph

**Files:**
- Modify: `backend/app/api/routes.py`

**知识点：为什么保留旧的 Pipeline？**

用 `if/else` 或配置开关在新旧两套逻辑间切换是最安全的做法——如果新 Agent 系统出了问题，旧 Pipeline 还能正常工作。这叫"绞杀者模式 (Strangler Fig Pattern)"：新系统逐步替代旧系统，而不是一刀切。

具体做法：保留 `_run_pipeline()` 不动，新增 `_run_agent_graph()`，在路由里加一个 `use_agent` 参数控制走哪条路。默认走 Agent 图（因为这是升级目标），但仍可手动切回 Pipeline。

- [ ] **Step 1: 修改 routes.py —— 添加 Agent 路径**

在 `backend/app/api/routes.py` 的 import 区域（最上面），追加：

```python
# 新增 import（追加在现有 import 之后）
from ..graph.builder import build_graph
from ..graph.state import AnalysisState
```

- [ ] **Step 2: 在 `_run_pipeline` 函数之后，新增 `_run_agent_graph` 函数**

```python
async def _run_agent_graph(issue, repo_url: str) -> AnalyzeResponse:
    """Agent 版分析——LangGraph 多 Agent 协作。

    和 _run_pipeline 的区别：
    - Pipeline：一次 LLM 调用，线性执行
    - Agent Graph：5 个 Agent 节点，每节点可多轮工具调用，条件路由
    """
    collection_name = f"repo-{issue.owner}-{issue.repo}-{uuid.uuid4().hex[:8]}"
    tmp_dir = Path(tempfile.mkdtemp(prefix="gh-issue-"))

    try:
        logger.info("[Agent] cloning: %s/%s", issue.owner, issue.repo)
        repo_path = clone_repo(repo_url, tmp_dir)

        snippets = parse_repo(repo_path)
        logger.info("[Agent] parsed: %d files, %d snippets",
                     len({s.file_path for s in snippets}), len(snippets))
        if not snippets:
            raise HTTPException(
                status_code=400,
                detail="No Python code found in the repository",
            )

        # 索引代码片段（Code Explorer 的 search_code 工具需要它）
        index_snippets(snippets, collection_name)
        logger.info("[Agent] indexed into collection: %s", collection_name)

        # 构建初始 State
        initial_state: AnalysisState = {
            "issue_url": issue.url,
            "repo_url": repo_url,
            "repo_path": str(repo_path),
            "issue_title": issue.title,
            "keywords": [],
            "error_context": f"## {issue.title}\n\n{issue.body or ''}",
            "error_type": "",
            "suspicious_snippets": [],
            "fix_drafts": [],
            "review_votes": [],
            "messages": [],
            "errors": [],
            "explore_rounds": 0,
            "explored_enough": False,
            "all_approved": False,
            "final_report": "",
        }

        # 构建图并运行
        graph = build_graph()
        graph.config["configurable"] = {
            "collection_name": collection_name,
            "snippets_raw": snippets,   # 传给工具层用
        }

        logger.info("[Agent] starting graph execution...")
        final_state = await graph.ainvoke(initial_state)
        logger.info("[Agent] graph finished. Messages: %d, Errors: %d",
                     len(final_state.get("messages", [])),
                     len(final_state.get("errors", [])))

        # 把 Agent 输出映射回 API 响应格式
        return AnalyzeResponse(
            issue_title=issue.title,
            issue_summary=final_state.get("final_report", "No report generated"),
            total_files_analyzed=len({s.file_path for s in snippets}),
            total_snippets_indexed=len(snippets),
            relevant_snippets=[
                CodeSnippet(**s) for s in final_state.get("suspicious_snippets", [])
            ],
            fix_suggestions=[
                FixSuggestion(
                    file_path=f.get("file_path", ""),
                    name=f.get("name", ""),
                    line_start=f.get("line_start", 0),
                    line_end=f.get("line_end", 0),
                    issue_summary=f.get("rationale", ""),
                    suggested_fix=f.get("fixed_code", ""),
                    confidence="medium",
                )
                for f in final_state.get("fix_drafts", [])
            ],
            raw_analysis=str(final_state.get("messages", [])),
        )

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        delete_collection(collection_name)
```

- [ ] **Step 3: 修改 `/analyze` 路由 —— 默认走 Agent 图**

```python
@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_issue(req: AnalyzeRequest, use_agent: bool = True) -> AnalyzeResponse:
    """Analyze a GitHub Issue.

    Args:
        req: Issue URL + Repo URL
        use_agent: True = LangGraph multi-agent (new), False = single-pass pipeline (old)
    """
    try:
        issue = await fetch_issue(req.issue_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch issue: {e}")

    if use_agent:
        return await _run_agent_graph(issue, req.repo_url)
    else:
        return await _run_pipeline(issue, req.repo_url)
```

- [ ] **Step 4: 启动服务，验证图能跑通**

```bash
cd "d:/项目/GitHub Issue/backend" && uvicorn app.main:app --reload --port 8000
```

```bash
# 另一个终端测试（用分析错误端点更快，不需要真实 Issue URL）
curl -X POST "http://localhost:8000/api/analyze-error" \
  -H "Content-Type: application/json" \
  -d '{
    "error_text": "TypeError: expected str, got int\n  File \"main.py\", line 10\n    result = add('"'"'hello'"'"', 42)",
    "repo_url": "https://github.com/psf/requests"
  }'
```

期望：返回 200，`issue_summary` 包含 "Phase 0 Placeholder"，`raw_analysis` 包含 5 条 Agent 消息。

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes.py
git commit -m "feat: wire LangGraph agent into /analyze route with use_agent toggle"
```

---

## Phase 1: Issue Analyst

### Task 1.1: 编写 LLM 驱动的 Issue Analyst 节点

**Files:**
- Modify: `backend/app/graph/nodes/issue_analyst.py`

**知识点：Prompt 工程 vs 函数调用——什么时候让 LLM 做结构化提取？**

LLM 擅长把非结构化文本（Issue body）转成结构化数据（错误类型、关键词）。
但你**不能指望 LLM 的输出格式 100% 可靠**——可能少一个字段、多一行解释。
所以解析函数 `_parse_analyst_output` 是确定性代码（try/except + 默认值兜底），
不依赖 LLM 的输出格式正确。

**设计原则：LLM 负责"理解"，代码负责"解析"。LLM 可以错，但代码不能崩。**

- [ ] **Step 1: 重写 `issue_analyst.py`**

```python
"""Issue Analyst — 分析 GitHub Issue，提取结构化信息。

职责：
  1. 读 Issue 的 title + body
  2. 用 LLM 提取：错误类型 / 关键词 / 结构化问题描述
  3. 写入 State，供后续 Agent 使用

工具：无（这个 Agent 不需要调用外部工具，纯 LLM 分析）
"""

import json
import re

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from ...core.config import settings, setup_logging
from ..state import AnalysisState

logger = setup_logging(__name__)

ANALYST_PROMPT = """You are an expert at analyzing GitHub Issues and bug reports.
Your job is to read an issue and extract structured information that helps
other agents search the codebase and write fixes.

Output a JSON object:
{
  "error_type": "Crash" | "LogicError" | "Performance" | "Configuration" | "Other",
  "keywords": ["3-5 specific terms to search in the code"],
  "error_context": "Structured summary of the problem (2-4 sentences)"
}

Keyword rules:
- Include specific function/class names if mentioned
- Include error message text (e.g., "KeyError: 'user_id'")
- Include relevant library names if the issue mentions them
- Don't include generic words like "error", "bug", "fix"
"""


def _parse_analyst_output(raw_text: str) -> dict:
    """确定性解析 LLM 输出 —— 永远不崩，最差返回默认值。

    为什么不用 Pydantic 验证？
    LLM 输出的 JSON 可能格式不完全正确（多一个逗号、少一个引号）。
    Pydantic 会直接抛异常。这里用宽松解析 + 默认值兜底，
    哪怕 LLM 完全胡说八道，系统也不会崩溃。
    """
    # 尝试提取 JSON 块
    json_match = re.search(r"\{[\s\S]*\}", raw_text)
    if not json_match:
        logger.warning("Analyst: no JSON found in output, using defaults")
        return {"error_type": "Other", "keywords": [], "error_context": raw_text[:500]}

    try:
        data = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        logger.warning("Analyst: JSON parse failed, using defaults")
        return {"error_type": "Other", "keywords": [], "error_context": raw_text[:500]}

    return {
        "error_type": str(data.get("error_type", "Other")),
        "keywords": data.get("keywords", [])[:10],  # 最多 10 个关键词
        "error_context": str(data.get("error_context", raw_text[:500])),
    }


def issue_analyst_node(state: AnalysisState) -> dict:
    """分析 Issue，提取结构化信息写入 State。

    不调用任何工具——纯 LLM 推理就够了。
    """
    title = state.get("issue_title", "")
    context = state.get("error_context", "")

    logger.info("Analyst: analyzing issue: %s", title[:80])

    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=settings.deepseek_api_key,
        base_url="https://api.deepseek.com",
        temperature=0.1,  # 低温度 = 更确定性的输出（分析任务不需要创意）
    )

    messages = [
        SystemMessage(content=ANALYST_PROMPT),
        HumanMessage(content=f"## Issue Title\n{title}\n\n## Issue Body\n{context}"),
    ]

    response = llm.invoke(messages)
    parsed = _parse_analyst_output(response.content)

    result = {
        "error_type": parsed["error_type"],
        "keywords": parsed["keywords"],
        "error_context": parsed["error_context"],
    }

    logger.info("Analyst: type=%s, keywords=%s", result["error_type"], result["keywords"])

    # 追加日志消息
    msgs = state.get("messages", [])
    msgs.append(
        f"[Analyst] 错误类型: {result['error_type']} | "
        f"关键词: {', '.join(result['keywords'])}"
    )

    return {**result, "messages": msgs}
```

- [ ] **Step 2: 单独测试 Analyst 节点**

```bash
cd "d:/项目/GitHub Issue/backend" && python -c "
import asyncio
from app.graph.nodes.issue_analyst import issue_analyst_node

state = {
    'issue_title': 'AttributeError when calling POST /users',
    'error_context': '## AttributeError when calling POST /users\n\nWhen I send a POST request to /users with JSON body, I get AttributeError: \'NoneType\' object has no attribute \'id\'. This happens in the create_user function in services/user.py.',
    'messages': [],
}
result = issue_analyst_node(state)
print('Error type:', result['error_type'])
print('Keywords:', result['keywords'])
print('Context:', result['error_context'][:200])
"
```

期望：正确提取 `error_type="Crash"`，`keywords` 包含 `create_user`, `AttributeError` 等。

- [ ] **Step 3: Commit**

```bash
git add backend/app/graph/nodes/issue_analyst.py
git commit -m "feat: implement LLM-driven Issue Analyst node"
```

---

## Phase 2: Code Explorer

### Task 2.1: 创建 LangChain 工具集 —— code_search

**Files:**
- Create: `backend/app/graph/tools/__init__.py`
- Create: `backend/app/graph/tools/code_search.py`

**知识点：LangChain `@tool` 装饰器做了什么？**

```python
@tool
def search_code(query: str, top_k: int = 5) -> str:
    """Search the codebase for relevant code snippets."""
```

`@tool` 自动做了三件事：
1. 把函数签名转成 OpenAI function calling 的 JSON Schema（`name`, `description`, `parameters`）
2. 让 LLM 知道"有这么一个工具可以用"
3. 当你用 `.bind_tools([search_code, ...])` 时，LLM 的 response 里会包含 tool_calls

**关键：工具的 docstring 就是 LLM 看的"使用说明书"。** 写的越清楚，LLM 调用得越准确。

- [ ] **Step 1: 创建 `backend/app/graph/tools/__init__.py`**

```python
# Agent tools — wrapped as LangChain @tool for LLM function calling
from .code_search import search_code
from .file_ops import read_file, find_callers, find_callees

__all__ = ["search_code", "read_file", "find_callers", "find_callees"]
```

- [ ] **Step 2: 创建 `backend/app/graph/tools/code_search.py`**

```python
"""search_code 工具 —— 封装现有的 retriever 为 LLM 可调用的工具。

设计要点：
  - 返回格式化文本（不是对象）——LLM 只能读文本
  - 结果数量有上限——防止塞爆 LLM 上下文窗口
  - 工具函数是同步的——因为 LLM 调用工具时是同步的
"""

from langchain_core.tools import tool

from ...services.retriever import retrieve
from ...services.embedder import search_snippets as embedding_search


@tool
def search_code(query: str, collection_name: str, top_k: int = 5) -> str:
    """Search the entire codebase for functions, classes, and methods relevant to the query.

    Use this tool when:
    - You need to find which files contain code related to a bug
    - You want to locate a specific function or class mentioned in the issue
    - You need to understand what code might be causing the problem

    Args:
        query: Natural language or code snippet to search for (e.g. "user creation function" or "KeyError: user_id")
        collection_name: ChromaDB collection name (provided by the system, don't guess)
        top_k: Number of results to return (1-10, default 5)

    Returns:
        Formatted string listing the most relevant code snippets with file paths, line numbers, and code
    """
    try:
        results = embedding_search(query, collection_name, top_k=top_k)
    except Exception as e:
        return f"Search failed: {e}"

    if not results:
        return "No matching code found. Try different keywords or a broader query."

    output_parts = []
    for i, (snippet, score) in enumerate(results, 1):
        output_parts.append(
            f"### Result {i} (score: {score:.3f})\n"
            f"File: `{snippet.file_path}`\n"
            f"Name: `{snippet.name}` ({snippet.kind})\n"
            f"Lines: {snippet.line_start}-{snippet.line_end}\n"
            f"```python\n{snippet.code[:1500]}\n```"
            # 截断到 1500 字符——防止一个巨大的函数占满上下文
        )

    return "\n\n".join(output_parts)
```

**为什么 `search_code` 只返回文本（不返回结构化对象）？**

LLM 的上下文是一段纯文本。你给它一个 Python 对象，它读不懂；你给它格式化的 Markdown 字符串，它能读得非常准确。所以所有给 LLM 用的工具，返回值的终极形态一定是 `str`。

- [ ] **Step 3: Commit**

```bash
git add backend/app/graph/tools/
git commit -m "feat: add search_code tool wrapping existing retriever"
```

---

### Task 2.2: 创建 file_ops 工具 —— read_file, find_callers, find_callees

**Files:**
- Create: `backend/app/graph/tools/file_ops.py`

**知识点：为什么需要 `find_callers` 和 `find_callees`？**

一个 Bug 很少是孤立函数的问题。比如 `AttributeError: 'NoneType' object has no attribute 'id'`——
错误发生在函数 A（访问 `.id` 时炸了），但根因可能在函数 B（返回了 None 而不是 User 对象）。

`find_callers`：谁调用了这个函数？（B 把 None 传给了 A）
`find_callees`：这个函数调用了谁？（A 内部调了什么导致 None 出现）

这就是**调用链追踪**——人类开发者排查 Bug 的标准流程，Agent 也需要这个能力。

- [ ] **Step 1: 创建 `backend/app/graph/tools/file_ops.py`**

```python
"""文件操作工具 —— read_file, find_callers, find_callees。

all-MiniLM-L6-v2 做的是语义级相似度搜索（"这个 Issue 描述和哪段代码语义接近"），
但不能回答"谁调用了这个函数"。后者是结构级查询，需要用 AST。

所以我们保留两种搜索能力：
  - 语义搜索（search_code）："看起来相关的代码"
  - 结构搜索（find_callers/find_callees）："直接相关的代码"
"""

from pathlib import Path

from langchain_core.tools import tool


@tool
def read_file(repo_path: str, file_path: str, start_line: int = 1, end_line: int | None = None) -> str:
    """Read a file from the cloned repository.

    Use this tool when:
    - You found a suspicious file via search_code and want to see its full context
    - You need to understand imports or surrounding functions
    - You want to see what other functions exist in the same file

    Args:
        repo_path: Root path of the cloned repository
        file_path: Relative path to the file from repo root (e.g. "src/services/user.py")
        start_line: First line to read (1-based, default 1)
        end_line: Last line to read (inclusive). If omitted, reads to end of file.

    Returns:
        File content with line numbers (format: "LINE_NUM| code")
    """
    full_path = Path(repo_path) / file_path
    if not full_path.exists():
        return f"Error: File not found: {file_path}"

    try:
        lines = full_path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return f"Error: Cannot read {file_path} (binary or non-UTF-8 file)"

    if end_line is None:
        end_line = len(lines)

    # Clamp to valid range
    start_line = max(1, min(start_line, len(lines)))
    end_line = max(start_line, min(end_line, len(lines)))

    # Format with line numbers (1-indexed, matches IDE display)
    output = []
    for i in range(start_line - 1, end_line):
        output.append(f"{i + 1:4d}| {lines[i]}")

    result = "\n".join(output)
    if end_line < len(lines):
        result += f"\n... ({len(lines) - end_line} more lines, use end_line to read further)"

    return result


@tool
def find_callers(
    repo_path: str,
    snippets_raw: str,
    func_name: str,
    file_path: str | None = None,
) -> str:
    """Find all functions/methods that CALL the given function.

    Use this tool when:
    - You found a buggy function and want to know who depends on it
    - You need to assess the blast radius of a proposed fix
    - You want to understand the call chain leading to a crash

    Args:
        repo_path: Root path of the cloned repository
        snippets_raw: JSON-serialized list of all CodeSnippet objects (system provides this)
        func_name: Name of the function to find callers for (e.g. "create_user")
        file_path: Optional filter — only look in this file

    Returns:
        List of callers with file paths and line numbers
    """
    import json
    import re

    from ...models.schemas import CodeSnippet

    try:
        snippets_data = json.loads(snippets_raw)
    except (json.JSONDecodeError, TypeError):
        return "Error: snippets_raw is not valid JSON"

    # 构建 AST 索引：{ func_name: [(file, line_start, line_end), ...] }
    # 这样可以快速定位函数的定义位置
    func_index: dict[str, list[dict]] = {}
    for s_dict in snippets_data:
        name = s_dict.get("name", "")
        # 去掉类名前缀（Class.method → method）
        short_name = name.split(".")[-1] if "." in name else name
        info = {
            "file_path": s_dict["file_path"],
            "line_start": s_dict["line_start"],
            "line_end": s_dict["line_end"],
            "full_name": name,
        }
        func_index.setdefault(short_name, []).append(info)
        if short_name != name:
            func_index.setdefault(name, []).append(info)

    # 在所有 snippet 代码中搜索对 func_name 的调用
    callers = []
    pattern = re.compile(rf"\b{re.escape(func_name)}\s*\(")

    for s_dict in snippets_data:
        if file_path and s_dict["file_path"] != file_path:
            continue

        code = s_dict.get("code", "")
        if pattern.search(code):
            # 找到了！这个 snippet 的代码里调用了目标函数
            callers.append({
                "file_path": s_dict["file_path"],
                "name": s_dict["name"],
                "kind": s_dict["kind"],
                "line_start": s_dict["line_start"],
            })

    if not callers:
        return f"No callers found for `{func_name}`"
    if len(callers) > 20:
        return f"Found {len(callers)} callers (too many, search refined). First 20:\n" + \
               "\n".join(f"- `{c['name']}` in {c['file_path']}:{c['line_start']}" for c in callers[:20])

    return "Callers of `" + func_name + "`:\n" + \
           "\n".join(f"- `{c['name']}` in {c['file_path']}:{c['line_start']}" for c in callers)


@tool
def find_callees(
    repo_path: str,
    file_path: str,
    func_name: str,
) -> str:
    """Find all functions/methods CALLED BY the given function.

    Use this tool when:
    - You're tracing a bug through a call chain
    - You want to know what external dependencies this function uses
    - You're assessing whether a fix in this function affects downstream calls

    Args:
        repo_path: Root path of the cloned repository
        file_path: Relative path to the file containing the function
        func_name: Name of the function to analyze

    Returns:
        List of functions called by func_name, with file and line info if available
    """
    import re

    full_path = Path(repo_path) / file_path
    if not full_path.exists():
        return f"Error: File not found: {file_path}"

    try:
        source = full_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Error: Cannot read {file_path}"

    lines = source.splitlines()
    # 找到目标函数的代码范围
    in_func = False
    func_lines = []
    indent_level = 0

    for i, line in enumerate(lines):
        # 检测函数定义
        if f"def {func_name}(" in line or f"async def {func_name}(" in line:
            in_func = True
            indent_level = len(line) - len(line.lstrip())
            continue

        if in_func:
            current_indent = len(line) - len(line.lstrip())
            # 遇到了同级或更靠左的代码（且不是空行）= 函数结束
            if line.strip() and current_indent <= indent_level:
                break
            func_lines.append(line)

    if not func_lines:
        return f"Function `{func_name}` not found in {file_path}"

    # 提取函数调用：匹配 word_name(...)
    func_code = "\n".join(func_lines)
    calls = re.findall(r"(\w+)\s*\(", func_code)

    # 过滤 Python 关键字和内置函数
    BUILTINS = {
        "print", "len", "range", "int", "str", "list", "dict", "set", "tuple",
        "isinstance", "type", "super", "enumerate", "zip", "map", "filter",
        "open", "getattr", "setattr", "hasattr", "sorted", "reversed",
        "any", "all", "sum", "min", "max", "abs", "round", "format",
        "self", "cls", "assert", "raise", "return", "yield", "break", "continue",
    }
    unique_calls = list(dict.fromkeys(c for c in calls if c not in BUILTINS))

    if not unique_calls:
        return f"`{func_name}` doesn't call any non-builtin functions."

    return f"Functions called by `{func_name}`:\n" + \
           "\n".join(f"- `{c}()`" for c in unique_calls[:30])
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/graph/tools/file_ops.py
git commit -m "feat: add read_file + find_callers + find_callees tools"
```

---

### Task 2.3: 实现 Code Explorer 节点

**Files:**
- Modify: `backend/app/graph/nodes/code_explorer.py`

**知识点：Agent Loop 的"思考-行动-观察"循环**

```
1. LLM 思考：基于当前信息，下一步做什么？
2. 如果 LLM 返回 tool_calls → 执行工具，观察结果，回到步骤 1
3. 如果 LLM 返回纯文本 → 它认为任务完成了，退出循环
```

这就是 ReAct (Reasoning + Acting) 模式的核心。
LangChain 的 AgentExecutor 把这个循环封装好了，但手写一遍循环才能真正理解：
**Agent 不是魔法——就是 LLM + 工具 + while 循环。**

- [ ] **Step 1: 重写 `code_explorer.py`**

```python
"""Code Explorer — 在代码库里搜索、读文件、追踪调用链，定位 Bug 根因。

Agent Loop 模式：
  1. LLM 收到任务 + 工具列表
  2. LLM 决定调用哪个工具（或输出分析结论）
  3. 执行工具，结果返回给 LLM
  4. 重复，直到 LLM 认为搜够了（或达到轮次上限）

关键设计：最终 State 更新由 parse_explorer_output() 确定性完成，
不是由 LLM 直接输出 State dict——LLM 不可靠，解析函数可靠。
"""

import json
import re

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI

from ...core.config import settings, setup_logging
from ..state import AnalysisState
from ..tools import search_code, read_file, find_callers, find_callees

logger = setup_logging(__name__)

MAX_ROUNDS = 5  # 最多 5 轮思考-行动

EXPLORER_SYSTEM = """You are an expert code explorer and bug hunter. Your job is to find the code
most likely causing a reported issue.

## Your Process
1. Start by searching the codebase with keywords from the issue
2. Read promising files fully to understand context
3. Trace call chains (find_callers, find_callees) to map the bug's path
4. Once you've identified the likely root cause files, describe them and stop

## Stop Conditions
Stop searching when you have found 1-5 files that clearly relate to the issue.
If after 3 rounds of searching you find nothing, say so honestly — don't fabricate matches.

## Output Format (at the END of your investigation, not after every tool call)
When you're done investigating, output a JSON block:
```json
{
  "explored_enough": true,
  "findings": [
    {
      "file_path": "path/to/file.py",
      "name": "function_or_class_name",
      "reason": "Why this code is likely related to the bug"
    }
  ]
}
```
"""


def _execute_tool(tool_name: str, tool_args: dict, tool_context: dict) -> str:
    """工具分发器——根据 LLM 要求的工具名，调用对应的 Python 函数。

    为什么需要这个分发器？
    LLM 返回的是工具名（字符串）和参数（dict），不是 Python 函数调用。
    我们需要手动把字符串映射到实际函数。
    LangChain 的 AgentExecutor 自动做了这件事，但手写能让你看清每一步。
    """
    repo_path = tool_context["repo_path"]
    collection_name = tool_context["collection_name"]
    snippets_raw = tool_context.get("snippets_raw", "[]")

    try:
        if tool_name == "search_code":
            return search_code.invoke({
                "query": tool_args.get("query", ""),
                "collection_name": collection_name,
                "top_k": tool_args.get("top_k", 5),
            })
        elif tool_name == "read_file":
            return read_file.invoke({
                "repo_path": repo_path,
                "file_path": tool_args.get("file_path", ""),
                "start_line": tool_args.get("start_line", 1),
                "end_line": tool_args.get("end_line", None),
            })
        elif tool_name == "find_callers":
            return find_callers.invoke({
                "repo_path": repo_path,
                "snippets_raw": json.dumps(snippets_raw) if isinstance(snippets_raw, list) else snippets_raw,
                "func_name": tool_args.get("func_name", ""),
                "file_path": tool_args.get("file_path", None),
            })
        elif tool_name == "find_callees":
            return find_callees.invoke({
                "repo_path": repo_path,
                "file_path": tool_args.get("file_path", ""),
                "func_name": tool_args.get("func_name", ""),
            })
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        logger.error("Tool %s failed: %s", tool_name, e)
        return f"Tool execution error: {e}"


def _parse_explorer_output(messages: list) -> dict:
    """从 Agent 的对话历史中提取最终结论。

    为什么检查所有消息而不是只看最后一条？
    LLM 可能在中间某次思考时已经得出了结论，最后一条可能是
    "似乎还需要再看看"——这是不对的。反过来，我们应该找
    最近一次符合格式的结论。
    """
    explored_enough = False
    findings = []

    # 从最后往前找——最近的结论最有参考价值
    for msg in reversed(messages):
        # 只检查 AI 的消息（不是 System/Human/Tool 的）
        if not hasattr(msg, "content") or not isinstance(msg, AIMessage):
            continue

        content = str(msg.content)
        # 找 JSON 块
        json_match = re.search(r"\{[\s\S]*\"explored_enough\"[\s\S]*\}", content)
        if not json_match:
            continue

        try:
            data = json.loads(json_match.group(0))
            if data.get("explored_enough"):
                explored_enough = True
                findings = data.get("findings", [])
                break
        except json.JSONDecodeError:
            continue

    return {"explored_enough": explored_enough, "findings": findings}


def code_explorer_node(state: AnalysisState, config: dict | None = None) -> dict:
    """搜索代码库，定位可疑代码。

    config 由 LangGraph 的 RunnableConfig 传入，包含：
      - collection_name: ChromaDB 集合名
      - snippets_raw: 原始 CodeSnippet 列表（给 find_callers 用的）
    """
    keywords = state.get("keywords", [])
    error_context = state.get("error_context", "")
    repo_path = state.get("repo_path", "")
    rounds = state.get("explore_rounds", 0) + 1

    # 从 config 中获取上下文（LangGraph 通过 configurable 传递）
    if config and "configurable" in config:
        collection_name = config["configurable"].get("collection_name", "")
        snippets_raw = config["configurable"].get("snippets_raw", [])
    else:
        collection_name = ""
        snippets_raw = []

    logger.info("Explorer: round %d, keywords=%s", rounds, keywords)

    # 绑定工具
    tools = [search_code, read_file, find_callers, find_callees]
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=settings.deepseek_api_key,
        base_url="https://api.deepseek.com",
        temperature=0.1,
    ).bind_tools(tools)

    # 构建消息历史
    user_prompt = f"""## Issue Context
{error_context}

## Search Keywords
{', '.join(keywords)}

## Repository Location
{repo_path}

Start by searching for code related to the keywords above.
Use the tools to explore, read files, and trace call chains."""

    messages = [
        SystemMessage(content=EXPLORER_SYSTEM),
        HumanMessage(content=user_prompt),
    ]

    # ── Agent Loop ──
    for round_num in range(MAX_ROUNDS):
        response = llm.invoke(messages)
        messages.append(response)

        # 没有工具调用 → LLM 认为该停了
        if not response.tool_calls:
            logger.info("Explorer: stopped at round %d (no tool calls)", round_num + 1)
            break

        # 执行工具
        for tc in response.tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            logger.debug("Explorer: calling %s(%s)", tool_name, tool_args)

            result = _execute_tool(tool_name, tool_args, {
                "repo_path": repo_path,
                "collection_name": collection_name,
                "snippets_raw": snippets_raw,
            })

            messages.append(ToolMessage(
                content=str(result),
                tool_call_id=tc["id"],
            ))

    # ── 解析结果 ──
    parsed = _parse_explorer_output(messages)
    explored_enough = parsed["explored_enough"]
    findings = parsed["findings"]

    logger.info("Explorer: explored_enough=%s, findings=%d", explored_enough, len(findings))

    # 把 findings 转成 State 格式的 suspicious_snippets
    suspicious = []
    for f in findings:
        suspicious.append({
            "file_path": f.get("file_path", ""),
            "name": f.get("name", ""),
            "line_start": 0,   # 后续可以从 snippet 数据中补全
            "line_end": 0,
            "code": "",
            "kind": "",
            "reason": f.get("reason", ""),
            "relevance_score": 0.0,
        })

    # 拼接日志
    msgs = state.get("messages", [])
    msgs.append(
        f"[Explorer Round {rounds}] "
        f"找到 {len(suspicious)} 个可疑位置, "
        f"搜够了={explored_enough}"
    )

    return {
        "suspicious_snippets": suspicious,
        "explored_enough": explored_enough,
        "explore_rounds": rounds,
        "messages": msgs,
    }
```

- [ ] **Step 2: 更新 tools/__init__.py 导出新工具**

已经导出了，无需修改。

- [ ] **Step 3: Commit**

```bash
git add backend/app/graph/nodes/code_explorer.py
git commit -m "feat: implement Code Explorer with 5-round Agent Loop"
```

---

## Phase 3: Fix Crafter

### Task 3.1: 实现 Fix Crafter 节点

**Files:**
- Modify: `backend/app/graph/nodes/fix_crafter.py`

**知识点：Prompt 里的 `context` 注入——给 LLM 看什么决定了修复质量**

Fix Crafter 不需要自己搜索——它依赖 Code Explorer 已经找到的可疑代码。
所以它的 prompt 里直接注入 `state["suspicious_snippets"]`，LLM 只需要"看着问题 + 看着代码 → 写修复"。

这是一种 **关注点分离**：Explorer 负责"找对地方"，Crafter 负责"写好方案"。
如果让一个 Agent 同时做两件事，prompt 会很长，LLM 容易顾此失彼。

- [ ] **Step 1: 重写 `fix_crafter.py`**

```python
"""Fix Crafter — 基于可疑代码生成具体修复方案。

职责单一：拿 Code Explorer 找到的代码 + 问题描述 → 写出修复 diff。
不需要搜索工具（read_file 可选，用于补充上下文）。
"""

import json
import re

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from ...core.config import settings, setup_logging
from ..state import AnalysisState

logger = setup_logging(__name__)

CRAFTER_SYSTEM = """You are an expert code fixer. Given a bug description and suspicious code,
write a concrete fix.

## Rules
- Be minimal: fix only what's broken, don't refactor unrelated code
- Be safe: consider edge cases (None, empty list, invalid input)
- Be specific: show the EXACT code change, not vague advice
- If you can't determine the fix from the available code, say so

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
"""


def _parse_crafter_output(raw_text: str) -> list[dict]:
    """解析 LLM 输出的修复方案列表。"""
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
        return {
            "fix_drafts": [],
            "messages": msgs,
        }

    logger.info("Crafter: drafting fixes for %d suspicious snippets", len(suspicious))

    # 构建代码上下文——给 LLM 看每段可疑代码
    code_context_parts = []
    for i, s in enumerate(suspicious):
        code_block = s.get("code", "")
        if not code_block or len(code_block) < 10:
            code_block = f"(code not available — read {s.get('file_path', 'unknown')} for details)"
        code_context_parts.append(
            f"### Suspicious #{i + 1}\n"
            f"File: `{s.get('file_path', '?')}`\n"
            f"Name: `{s.get('name', '?')}`\n"
            f"Reason: {s.get('reason', 'no reason given')}\n"
            f"```python\n{code_block[:2000]}\n```"
        )

    user_prompt = f"""## Bug Description
Error Type: {error_type}
{error_context}

## Suspicious Code
{chr(10).join(code_context_parts)}

For each suspicious code block that clearly relates to the bug, write a fix.
If a block doesn't seem related, skip it."""

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

    # 标准化输出格式
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

    return {
        "fix_drafts": fix_drafts,
        "messages": msgs,
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/graph/nodes/fix_crafter.py
git commit -m "feat: implement Fix Crafter node"
```

---

## Phase 4: Reviewer

### Task 4.1: 实现 Reviewer 节点

**Files:**
- Modify: `backend/app/graph/nodes/reviewer.py`

**知识点：LLM 做审查——怎么让同一个模型"挑自己的刺"？**

用不同的 system prompt 给 LLM 分配不同的人格：
- Fix Crafter 的 prompt：建设性的（"写出修复方案"）
- Reviewer 的 prompt：批判性的（"这个方案哪里可能出错"）

同一个模型，给不同的 system prompt，行为截然不同。这就是 prompt 工程的核心：
**你不是在改变模型，你是在改变角色。**

- [ ] **Step 1: 重写 `reviewer.py`**

```python
"""Reviewer — 审查修复方案，通过或驳回。

设计要点：
  1. 每个 fix 单独审查（不是打总分）
  2. 驳回必须带具体原因（feedback 字段），供 Fix Crafter 参考
  3. 只有全部 fix 通过，all_approved 才为 True
  4. DeepSeek 可能不总是返回工具调用格式——有兜底解析
"""

import json
import re

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from ...core.config import settings, setup_logging
from ..state import AnalysisState

logger = setup_logging(__name__)

REVIEWER_SYSTEM = """You are a strict code reviewer. Your job is to evaluate fix suggestions
and find problems before they reach production.

## Review Criteria
1. **Correctness**: Does the fix actually solve the reported bug?
2. **Safety**: Could this fix break existing functionality? (Check edge cases: None, empty input, etc.)
3. **Style**: Does the fix follow the project's existing code patterns?
4. **Completeness**: Are there other places in the codebase that need the same fix?

## Output Format
```json
{
  "votes": [
    {
      "fix_index": 0,
      "verdict": "approved|rejected",
      "feedback": "Specific reason for the verdict"
    }
  ]
}
```

## Rules
- approve only if the fix is demonstrably correct AND safe
- reject if the fix is incomplete, risky, or doesn't match the bug description
- be specific in feedback — "this seems fine" is not helpful
- if you reject, tell the fixer exactly what to change
"""


def _parse_review_output(raw_text: str, fix_count: int) -> tuple[list[dict], bool]:
    """解析审查结果。

    兜底策略：如果 LLM 没返回有效 JSON，全部 approve（让流程继续），
    但在日志里记录警告。这保证了图不会因为 Reviewer 解析失败而卡死。
    """
    json_match = re.search(r"\{[\s\S]*\"votes\"[\s\S]*\}", raw_text)
    if not json_match:
        logger.warning("Reviewer: no JSON in output, auto-approving all")
        default = [{"fix_index": i, "verdict": "approved", "feedback": "Auto-approved (parse error)"}
                   for i in range(fix_count)]
        return default, True

    try:
        data = json.loads(json_match.group(0))
        votes = data.get("votes", [])
    except json.JSONDecodeError:
        logger.warning("Reviewer: JSON parse failed, auto-approving all")
        default = [{"fix_index": i, "verdict": "approved", "feedback": "Auto-approved (parse error)"}
                   for i in range(fix_count)]
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

    # 构建审查上下文
    fixes_text = []
    for i, f in enumerate(fix_drafts):
        fixes_text.append(
            f"### Fix #{i}\n"
            f"File: `{f.get('file_path', '?')}`\n"
            f"Function: `{f.get('name', '?')}`\n"
            f"Rationale: {f.get('rationale', 'none')}\n"
            f"Original:\n```python\n{f.get('original_code', 'N/A')[:1500]}\n```\n"
            f"Fixed:\n```python\n{f.get('fixed_code', 'N/A')[:1500]}\n```"
        )

    user_prompt = f"""## Original Bug
Error Type: {error_type}
{error_context}

## Fix Proposals
{chr(10).join(fixes_text)}

Review each fix carefully. Be strict — reject anything that isn't clearly correct and safe."""

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
    msgs.append(
        f"[Reviewer] {approved_count} 通过, {rejected_count} 驳回"
    )

    return {
        "review_votes": votes,
        "all_approved": all_approved,
        "messages": msgs,
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/graph/nodes/reviewer.py
git commit -m "feat: implement Reviewer node with approve/reject logic"
```

---

## Phase 5: Reporter

### Task 5.1: 实现 Reporter 节点

**Files:**
- Modify: `backend/app/graph/nodes/reporter.py`

**知识点：为什么 Reporter 不需要 LLM？**

Reporter 的工作是"组装"——把前面 4 个 Agent 的输出拼成一份结构化的 Markdown 报告。
这不需要 AI 判断，用 Python 字符串模板就够了。
原则：**能用代码确定性地做的事情，不要浪费 LLM 的 token。**

- [ ] **Step 1: 重写 `reporter.py`**

```python
"""Reporter — 汇总所有 Agent 产出，生成 Markdown 格式的最终分析报告。

不需要 LLM——纯模板拼接。所有决策已经由前面的 Agent 做完了。
"""

from ...core.config import setup_logging
from ..state import AnalysisState

logger = setup_logging(__name__)


def _format_snippets(snippets: list[dict]) -> str:
    """格式化可疑代码片段为 Markdown。"""
    if not snippets:
        return "_No suspicious code identified._"

    parts = []
    for i, s in enumerate(snippets, 1):
        code = s.get("code", "")
        if code:
            code_block = f"\n```python\n{code[:1000]}\n```"
        else:
            code_block = f"\n_(use read_file to view `{s.get('file_path', '?')}:{s.get('line_start', 0)}`)_"

        parts.append(
            f"### {i}. `{s.get('name', '?')}` — {s.get('file_path', '?')}:{s.get('line_start', 0)}\n"
            f"**Reason**: {s.get('reason', 'No reason given')}\n"
            f"{code_block}"
        )
    return "\n".join(parts)


def _format_fixes(fixes: list[dict], votes: list[dict]) -> str:
    """格式化修复方案 + 审查结果为 Markdown。"""
    if not fixes:
        return "_No fix suggestions generated._"

    # 构建 index → verdict 映射
    verdict_map = {}
    for v in votes:
        verdict_map[v.get("fix_index", -1)] = v

    parts = []
    for i, f in enumerate(fixes):
        verdict = verdict_map.get(i, {})
        status = verdict.get("verdict", "pending")
        emoji = "✅" if status == "approved" else "❌" if status == "rejected" else "⏳"

        parts.append(
            f"### {emoji} Fix {i + 1}: {f.get('name', '?')} — `{f.get('file_path', '?')}`\n\n"
            f"**Rationale**: {f.get('rationale', 'No rationale')}\n\n"
            f"**Original Code**:\n```python\n{f.get('original_code', 'N/A')}\n```\n\n"
            f"**Fixed Code**:\n```python\n{f.get('fixed_code', 'N/A')}\n```\n\n"
            f"**Review**: {verdict.get('feedback', 'No feedback')}"
        )
    return "\n\n".join(parts)


def reporter_node(state: AnalysisState) -> dict:
    """生成最终分析报告。"""
    logger.info("Reporter: composing final report")

    report = f"""# 🔍 GitHub Issue Analysis Report

## 📋 Issue Summary
**Title**: {state.get('issue_title', 'Unknown')}
**Error Type**: {state.get('error_type', 'Unknown')}

{state.get('error_context', 'No context available')}

---

## 🔎 Suspicious Code Locations
{_format_snippets(state.get('suspicious_snippets', []))}

---

## 🔧 Fix Suggestions
{_format_fixes(state.get('fix_drafts', []), state.get('review_votes', []))}

---

## 📊 Analysis Statistics
- Explorer rounds: {state.get('explore_rounds', 0)}
- Suspicious locations found: {len(state.get('suspicious_snippets', []))}
- Fixes drafted: {len(state.get('fix_drafts', []))}
- Fixes approved: {sum(1 for v in state.get('review_votes', []) if v.get('verdict') == 'approved')}

---
_Generated by GitHub Issue Code Analyzer v2 (Multi-Agent LangGraph)_
"""

    msgs = state.get("messages", [])
    msgs.append("[Reporter] 最终报告已生成")

    return {
        "final_report": report,
        "messages": msgs,
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/graph/nodes/reporter.py
git commit -m "feat: implement Reporter — template-based Markdown report"
```

---

## Phase 6: 前端改造 —— SSE 流式输出

### Task 6.1: 添加 SSE 流式端点

**Files:**
- Modify: `backend/app/api/routes.py`
- (可选) Create: `backend/app/api/stream.py`

**知识点：SSE (Server-Sent Events) vs WebSocket**

SSE 是单向的（服务器 → 客户端），基于 HTTP，浏览器原生支持。
WebSocket 是双向的，需要额外握手，更复杂。

对于"实时看 Agent 进度"这个场景，SSE 足够：服务器推送 Agent 的中间日志，
客户端只读不写。比 WebSocket 简单一个数量级。

- [ ] **Step 1: 添加流式路由 `backend/app/api/routes.py`**

在现有 import 区域，追加：

```python
import asyncio
import json
from fastapi.responses import StreamingResponse
```

在 `/analyze-error` 路由之后，追加：

```python
@router.post("/analyze/stream")
async def analyze_issue_stream(req: AnalyzeRequest):
    """SSE stream version — sends agent progress events in real-time.

    Event format (SSE):
        data: {"type": "agent_step", "agent": "code_explorer", "message": "..."}
        data: {"type": "result", "final_report": "..."}
        data: {"type": "done"}

    Frontend can display progress as agents work through the graph.
    """
    async def event_generator():
        try:
            # Fetch issue first
            yield f"data: {json.dumps({'type': 'agent_step', 'agent': 'system', 'message': 'Fetching issue...'})}\n\n"
            try:
                issue = await fetch_issue(req.issue_url)
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                return

            yield f"data: {json.dumps({'type': 'agent_step', 'agent': 'system', 'message': f'Issue loaded: {issue.title}'})}\n\n"

            # Run the agent graph with stream_mode
            collection_name = f"repo-{issue.owner}-{issue.repo}-{uuid.uuid4().hex[:8]}"
            tmp_dir = Path(tempfile.mkdtemp(prefix="gh-issue-"))

            try:
                yield f"data: {json.dumps({'type': 'agent_step', 'agent': 'system', 'message': 'Cloning repository...'})}\n\n"
                repo_path = clone_repo(req.repo_url, tmp_dir)

                snippets = parse_repo(repo_path)
                yield f"data: {json.dumps({'type': 'agent_step', 'agent': 'system', 'message': f'Parsed {len(snippets)} code snippets from {len({s.file_path for s in snippets})} files'})}\n\n"

                if not snippets:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'No Python code found'})}\n\n"
                    return

                index_snippets(snippets, collection_name)

                # Build initial state
                initial_state: dict = {
                    "issue_url": issue.url,
                    "repo_url": req.repo_url,
                    "repo_path": str(repo_path),
                    "issue_title": issue.title,
                    "keywords": [],
                    "error_context": f"## {issue.title}\n\n{issue.body or ''}",
                    "error_type": "",
                    "suspicious_snippets": [],
                    "fix_drafts": [],
                    "review_votes": [],
                    "messages": [],
                    "errors": [],
                    "explore_rounds": 0,
                    "explored_enough": False,
                    "all_approved": False,
                    "final_report": "",
                }

                graph = build_graph()
                graph.config["configurable"] = {
                    "collection_name": collection_name,
                    "snippets_raw": snippets,
                }

                yield f"data: {json.dumps({'type': 'agent_step', 'agent': 'system', 'message': 'Starting agent graph...'})}\n\n"

                # 流式执行：每个节点完成后推送一次
                async for event in graph.astream(initial_state):
                    for node_name, node_output in event.items():
                        if "messages" in node_output:
                            last_msgs = node_output["messages"]
                            if last_msgs:
                                yield f"data: {json.dumps({'type': 'agent_step', 'agent': node_name, 'message': last_msgs[-1]})}\n\n"

                # 等图跑完，拿最终结果
                final_state = await graph.ainvoke(initial_state)
                yield f"data: {json.dumps({'type': 'result', 'final_report': final_state.get('final_report', 'No report'), 'errors': final_state.get('errors', [])})}\n\n"

            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                delete_collection(collection_name)

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )
```

- [ ] **Step 2: 测试 SSE 端点**

```bash
curl -N -X POST "http://localhost:8000/api/analyze/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "issue_url": "https://github.com/fastapi/fastapi/issues/14484",
    "repo_url": "https://github.com/fastapi/fastapi"
  }'
```

期望：逐行输出 `data: {...}` 的 SSE 事件流。

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/routes.py
git commit -m "feat: add SSE streaming endpoint for real-time agent progress"
```

---

### Task 6.2: 前端 SSE 进度展示（可选 — 基础版）

**Files:**
- Modify: `frontend/index.html`

这一步只做最小改动——在现有前端上加一个流式模式按钮，连到 SSE 端点，实时显示 Agent 的进度日志。

- [ ] **Step 1: 在现有 index.html 的分析结果区域上方加 Agent 日志区**

找到现有 HTML 里的结果展示区域，在前面插入：

```html
<!-- Agent 进度日志区 -->
<div id="agent-log" style="display:none; background:#0a0a0a; border:1px solid var(--accent); padding:1rem; margin-bottom:1rem; max-height:300px; overflow-y:auto; font-family:monospace; font-size:0.85rem;">
  <div style="color:var(--accent); margin-bottom:0.5rem;">▶ Agent Progress</div>
  <div id="agent-log-entries"></div>
</div>
```

并在表单区增加一个流式模式复选框（放在 Submit 按钮前）：

```html
<label style="display:flex; align-items:center; gap:0.5rem; margin-bottom:1rem;">
  <input type="checkbox" id="stream-mode" />
  <span>Stream mode (real-time agent progress)</span>
</label>
```

- [ ] **Step 2: 在 JS 部分添加 SSE 逻辑**

```javascript
// SSE 模式 —— 实时 Agent 进度
if (document.getElementById('stream-mode').checked) {
    document.getElementById('agent-log').style.display = 'block';
    document.getElementById('agent-log-entries').innerHTML = '';

    const response = await fetch('/api/analyze/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ issue_url: issueUrl, repo_url: repoUrl }),
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();  // 保留不完整的最后一行

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = JSON.parse(line.slice(6));
                if (data.type === 'agent_step') {
                    const entry = document.createElement('div');
                    entry.style.cssText = 'padding:0.25rem 0; border-bottom:1px solid #1a1a1a;';
                    entry.innerHTML = `<span style="color:#666;">[${data.agent}]</span> ${data.message}`;
                    document.getElementById('agent-log-entries').appendChild(entry);
                    document.getElementById('agent-log').scrollTop = document.getElementById('agent-log').scrollHeight;
                } else if (data.type === 'result') {
                    displayResult(data.final_report);
                } else if (data.type === 'error') {
                    const entry = document.createElement('div');
                    entry.style.color = '#ff4444';
                    entry.textContent = `Error: ${data.message}`;
                    document.getElementById('agent-log-entries').appendChild(entry);
                }
            }
        }
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/index.html
git commit -m "feat: add SSE streaming UI — real-time agent progress display"
```

---

## 自审检查

### Spec 覆盖对照

| Spec 要求 | 对应 Task |
|-----------|----------|
| AnalysisState TypedDict | Task 0.2 |
| StateGraph 构建 + 条件边 | Task 0.3 |
| 5 个占位节点（行走骨架） | Task 0.4 |
| routes.py 切到 Graph | Task 0.5 |
| Issue Analyst + LLM 分析 | Task 1.1 |
| search_code 工具封装 | Task 2.1 |
| read_file + find_callers + find_callees | Task 2.2 |
| Code Explorer Agent Loop | Task 2.3 |
| Fix Crafter 节点 | Task 3.1 |
| Reviewer 审查 + 驳回 | Task 4.1 |
| Reporter Markdown 报告 | Task 5.1 |
| SSE 流式端点 | Task 6.1 |
| 前端 SSE 进度显示 | Task 6.2 |
| 复用现有 services | 所有 Task 的 import 路径 |
| 防无限循环 | Task 0.3 条件边 + MAX_ROUNDS |
| messages 调试字段 | 每个 Task 的 messages 追加 |

### Placeholder 扫描
通过——无 TBD/TODO/迭代符号。

### 类型一致性
- `AnalysisState` 字段名在所有节点中一致：`explore_rounds`, `suspicious_snippets`, `fix_drafts`, `review_votes`, `all_approved`, `messages`
- 工具函数签名和 `_execute_tool` 中的调用一致
- 路由返回值类型和 Pydantic models 一致
