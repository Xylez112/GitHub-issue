# Multi-Agent System Design: GitHub Issue Code Analyzer v2

> **Status**: Approved — 2025-06-08
> **From**: MVP single-pass Pipeline → LangGraph-based Multi-Agent System

---

## 1. 决策记录

| 决策点 | 选项 |
|--------|------|
| Agent 协作模式 | B. 自由协作 (Swarm/Crew) — 无中心调度者，各 Agent 自行决定下一步 |
| Agent 间通信 | A. 共享消息总线 → 落地为 **LangGraph Shared State**（天然黑板模型） |
| Agent 角色 | 5 个全上：Issue Analyst, Code Explorer, Fix Crafter, Reviewer, Reporter |
| Agent 运行时 | B. **LangGraph** — StateGraph + 条件路由 + bind_tools |
| 整体节奏 | 一个模块一个模块上手，先理解原理再写代码 |

## 2. 现状

```
Issue URL → Fetch Issue → Clone Repo → Tree-sitter Parse
→ Embedding Index → BM25+Embedding Retrieve → Single LLM Call → Output
```

瓶颈：
- LLM 只有一次机会看代码，不能自主搜索
- 无工具调用能力，不能读文件、追踪调用链
- 无迭代 — 第一次检索不准就全军覆没
- 无验证 — 修复方案不经审查直接输出

## 3. 目标架构

```
                        ┌─────────────────────┐
                        │   LangGraph State    │
                        │  (共享上下文/黑板)    │
                        └──┬──┬──┬──┬──┬──────┘
                           │  │  │  │  │
              ┌────────────┼──┼──┼──┼──┼────────────┐
              │            │  │  │  │  │            │
              ▼            ▼  ▼  ▼  ▼  ▼            ▼
        Issue Analyst  Code Explorer  Fix Crafter  Reviewer  Reporter
              │            │              │           │         │
              └────────────┴──────────────┴───────────┴─────────┘
                    条件边 (Conditional Edges) 决定流转
```

核心差异：
- **从 Pipeline 到 Graph**：每个 Agent 是一个图节点，State 在节点间流转
- **从一次性到迭代**：Reviewer 可以驳回 → Fix Crafter 重改；Code Explorer 可以回头找 Analyst 澄清
- **从只看到能做**：每个 Agent 绑定工具（搜索、读文件、追踪调用链）

## 4. LangGraph 图结构

### 4.1 节点 (Nodes)

| 节点 | 工具集 | 职责 |
|------|--------|------|
| `issue_analyst` | `parse_issue` | 读 Issue → 提取错误类型、关键词、复现步骤 |
| `code_explorer` | `search_code`, `read_file`, `find_callers`, `find_callees` | 搜索代码库 → 读可疑文件 → 追踪调用链 → 定位根因 |
| `fix_crafter` | `read_file`, `write_fix` | 基于可疑代码 → 产出具体修复方案 (diff) |
| `reviewer` | `read_file`, `check_side_effects`, `check_style` | 审查修复 → 通过/驳回（带原因） |
| `reporter` | `compose_report` | 汇总所有产出 → 生成 Markdown 报告 |

### 4.2 条件边 (Conditional Edges) — 自由协作的引擎

```
issue_analyst ──→ code_explorer ──┬──→ fix_crafter ──→ reviewer ──┬──→ reporter
                                  │                                 │
                                  │  搜不到时回头找 Analyst          │  驳回时打回 Fix Crafter
                                  └──→ issue_analyst               └──→ fix_crafter
```

```python
def route_after_explore(state):
    if state["explored_enough"]:
        return "fix_crafter"
    elif state["explore_rounds"] > 5:
        return "issue_analyst"      # 关键词可能不对，回去重分析
    else:
        return "code_explorer"      # 继续搜

def route_after_review(state):
    if state["all_approved"]:
        return "reporter"
    else:
        return "fix_crafter"        # 拿反馈回去改
```

### 4.3 Shared State

```python
class AnalysisState(TypedDict):
    # ── 输入 ──
    issue_url: str
    repo_url: str
    repo_path: str              # clone 后的本地路径

    # ── Issue Analyst 产出 ──
    issue_title: str
    error_type: str             # "Crash" | "LogicError" | "Performance" | ...
    keywords: list[str]         # 搜索关键词列表
    error_context: str          # 结构化问题描述（给后续 Agent 看的）

    # ── Code Explorer 产出 ──
    suspicious_snippets: list[dict]   # [{file_path, name, line_start, line_end, code, reason}]
    explored_enough: bool
    explore_rounds: int               # 防无限循环

    # ── Fix Crafter 产出 ──
    fix_drafts: list[dict]      # [{file_path, original_code, fixed_code, rationale}]

    # ── Reviewer 产出 ──
    review_votes: list[dict]    # [{fix_index, verdict: "approved"|"rejected", feedback}]
    all_approved: bool

    # ── Reporter 产出 ──
    final_report: str           # Markdown

    # ── 全局 ──
    messages: list              # 所有 Agent 的对话记录（调试 + 审计用）
    errors: list[str]           # 运行期错误收集
```

## 5. 每个 Agent 的内部结构

以 `code_explorer` 为例，**所有 Agent 遵循同一模式**：

```python
def code_explorer_node(state: AnalysisState) -> dict:
    # 1. 绑定工具
    llm = ChatOpenAI(model="deepseek-chat").bind_tools([
        search_code,    # 复用现有 retriever
        read_file,       # 新增 — 读文件内容
        find_callers,    # 新增 — Tree-sitter 查调用者
        find_callees,    # 新增 — Tree-sitter 查被调用者
    ])

    # 2. 构造 prompt（注入当前 state 里的相关信息）
    system_prompt = """
    你是代码勘探专家。Issue 已经由 Analyst 分析好了。
    使用工具在代码库里搜索、读文件、追踪调用链。
    当你认为找到了与 Issue 相关的代码，标记 explored_enough = true。
    不要超过 5 轮工具调用。
    """

    user_prompt = f"""
    Issue 上下文: {state['error_context']}
    搜索关键词: {state['keywords']}
    仓库路径: {state['repo_path']}
    """

    # 3. Agent Loop（最多 5 轮思考-行动-观察）
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    for _ in range(5):
        response = llm.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            break   # LLM 认为不需要再查了

        for tc in response.tool_calls:
            result = execute_tool(tc)       # 实际执行
            messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

    # 4. 解析最终输出，更新 State
    return parse_explorer_output(messages, state)
```

这个模式的关键：**每个 Agent 拥有有限自主权（5 轮），但最终 State 更新由确定性解析函数完成，不依赖 LLM 自由发挥。**

## 6. 文件结构

```
backend/
├── app/
│   ├── main.py                 # FastAPI + LangGraph graph 挂载
│   ├── api/
│   │   └── routes.py           # POST /analyze → graph.ainvoke()
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py            # AnalysisState TypedDict
│   │   ├── builder.py          # StateGraph 构建 + 注册节点 + 条件边
│   │   ├── nodes/
│   │   │   ├── __init__.py
│   │   │   ├── issue_analyst.py
│   │   │   ├── code_explorer.py
│   │   │   ├── fix_crafter.py
│   │   │   ├── reviewer.py
│   │   │   └── reporter.py
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── code_search.py   # 封装现有 retriever + embedder
│   │       ├── file_ops.py      # read_file, find_callers, find_callees
│   │       └── fix_ops.py       # write_fix
│   ├── services/               # 保留现有 services（被 tools 调用）
│   │   ├── github.py
│   │   ├── code_parser.py      # Tree-sitter（直接复用）
│   │   ├── embedder.py          # ChromaDB（直接复用）
│   │   ├── bm25.py              # BM25（直接复用）
│   │   └── retriever.py         # 混合检索（直接复用）
│   ├── models/
│   │   └── schemas.py           # Pydantic models（扩展）
│   └── core/
│       └── config.py            # 配置（扩展 API keys）
├── tests/
│   ├── test_nodes/              # 每个节点独立测试
│   └── test_graph/              # 整图集成测试
└── frontend/
    └── index.html               # 改造成支持 SSE 流式输出
```

## 7. 技术选型总结

| 组件 | MVP 版 | Agent 版 | 理由 |
|------|--------|----------|------|
| 编排 | FastAPI route 直调函数 | **LangGraph StateGraph** | 有向图 + 条件路由 + 天然防无限循环 |
| LLM 调用 | 裸 `openai` SDK | **LangChain ChatModel + bind_tools** | 统一工具定义，和 LangGraph 配套 |
| 向量检索 | ChromaDB | ChromaDB（不变） | 现有代码成熟，包装成 tool 即可 |
| 代码解析 | Tree-sitter | Tree-sitter（不变） | 同上 |
| BM25 | 自实现 | 自实现（不变） | 同上 |
| API 框架 | FastAPI | FastAPI（不变） | 只加一个 `/analyze/stream` 端点 |
| 模型 | DeepSeek Chat | DeepSeek Chat（暂不变） | 成本和效果平衡，后续可切 Claude |
| 前端 | 单页 HTML | 改造为 SSE 流式接收 | 实时看 Agent 走到哪一步 |

## 8. 风险 + 缓解

| 风险 | 缓解 |
|------|------|
| LangGraph 学习曲线陡 | 先做一个最小图（2 个节点），跑通再扩展 |
| 自由协作导致无限循环 | `max_iterations` + `explore_rounds` 硬上限 + Reviewer 终局裁决 |
| DeepSeek 工具调用不稳定 | 每个节点的输出解析用确定性函数兜底，不纯靠 LLM |
| 多 Agent 调试困难 | `messages` 字段记录每个 Agent 的完整思考链，API 返回 |
| 费用爆炸 | 每个 Agent 限制 5 轮工具调用，全流程 ≤ 25 次 LLM 请求 |

## 9. 实施顺序（一个模块一个模块来）

| 阶段 | 内容 | 预估难度 |
|------|------|----------|
| **Phase 0** | 搭 LangGraph 骨架 — 两个空节点 + State + 条件边，能跑通 | ⭐ |
| **Phase 1** | Issue Analyst — 单一节点 + parse_issue 工具 | ⭐⭐ |
| **Phase 2** | Code Explorer — 封装现有 retriever 为 search_code 工具 + read_file | ⭐⭐⭐ |
| **Phase 3** | Fix Crafter — 基于 Explorer 结果生成 diff | ⭐⭐ |
| **Phase 4** | Reviewer — 审查 + 驳回逻辑 | ⭐⭐⭐ |
| **Phase 5** | Reporter — 组装最终报告 | ⭐ |
| **Phase 6** | 前端改造 — SSE 流式输出 + 状态可视化 | ⭐⭐ |
