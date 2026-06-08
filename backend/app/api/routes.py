import uuid
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..core.config import setup_logging
from ..models.schemas import (
    AnalyzeRequest, AnalyzeErrorRequest, AnalyzeResponse,
    CodeSnippet, FixSuggestion,
)
from ..services.github import fetch_issue, make_synthetic_issue, clone_repo
from ..services.code_parser import parse_repo
from ..services.embedder import index_snippets, delete_collection
from ..services.retriever import retrieve
from ..services.analyzer import analyze

# Agent 图相关
from ..graph.builder import build_graph
from ..graph.state import AnalysisState

logger = setup_logging(__name__)
router = APIRouter(prefix="/api", tags=["analyzer"])


async def _run_pipeline(issue, repo_url: str) -> AnalyzeResponse:
    """Shared pipeline: clone → parse → index → retrieve → analyze.

    Accepts any IssueData (from GitHub API or synthetic from raw error text).
    """
    collection_name = f"repo-{issue.owner}-{issue.repo}-{uuid.uuid4().hex[:8]}"
    tmp_dir = Path(tempfile.mkdtemp(prefix="gh-issue-"))

    try:
        logger.info("cloning: %s/%s", issue.owner, issue.repo)
        repo_path = clone_repo(repo_url, tmp_dir)

        snippets = parse_repo(repo_path)
        logger.info("parsed: %d files, %d snippets", len({s.file_path for s in snippets}), len(snippets))
        if not snippets:
            raise HTTPException(
                status_code=400,
                detail="No Python code found in the repository",
            )

        index_snippets(snippets, collection_name)
        logger.info("indexed into collection: %s", collection_name)

        results = retrieve(issue, collection_name, top_k=30, snippets=snippets)
        logger.info("retrieved: %d relevant snippets", len(results))

        relevant_snippets = [s for s, _ in results]
        raw_text, summary, fix_suggestions = await analyze(issue, results)
        logger.info("analysis complete: %d fix suggestions", len(fix_suggestions))

        return AnalyzeResponse(
            issue_title=issue.title,
            issue_summary=summary,
            total_files_analyzed=len({s.file_path for s in snippets}),
            total_snippets_indexed=len(snippets),
            relevant_snippets=relevant_snippets,
            fix_suggestions=fix_suggestions,
            raw_analysis=raw_text,
        )

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        delete_collection(collection_name)


async def _run_agent_graph(issue, repo_url: str) -> AnalyzeResponse:
    """Agent 版分析——LangGraph 多 Agent 协作。

    和 _run_pipeline 的区别：
    - Pipeline：一次 LLM 调用，线性执行
    - Agent Graph：5 个 Agent 节点，每节点可多轮工具调用，条件路由

    clone → parse → index 这部分两种模式共用（都是准备工作），
    差异在"分析"环节——Pipeline 调一次 analyze()，Graph 跑一整张图。
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

        # 索引代码片段——Code Explorer 的 search_code 工具通过
        # collection_name 找到对应的 ChromaDB 集合
        index_snippets(snippets, collection_name)
        logger.info("[Agent] indexed into collection: %s", collection_name)

        # 构建初始 State —— 只填入 API 层已知的信息
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

        # 构建图并注入"额外配置"——
        # LangGraph 的 configurable 字典会传递给每个节点函数
        # 节点通过 config["configurable"] 读取这些值
        graph = build_graph()

        logger.info("[Agent] starting graph execution...")
        final_state = await graph.ainvoke(
            initial_state,
            config={
                "configurable": {
                    "collection_name": collection_name,
                    "snippets_raw": snippets,   # 传给 Code Explorer 工具层
                }
            },
        )
        logger.info("[Agent] graph finished. Messages: %d, Errors: %d",
                     len(final_state.get("messages", [])),
                     len(final_state.get("errors", [])))

        # 把 Agent 的 State 输出映射回 API 响应格式
        # 这里做"格式转换"——Agent 内部用 dict，API 对外用 Pydantic Model
        return AnalyzeResponse(
            issue_title=issue.title,
            issue_summary=final_state.get("final_report", "No report generated"),
            total_files_analyzed=len({s.file_path for s in snippets}),
            total_snippets_indexed=len(snippets),
            relevant_snippets=[
                CodeSnippet(
                    file_path=s.get("file_path", ""),
                    name=s.get("name", ""),
                    line_start=s.get("line_start", 0),
                    line_end=s.get("line_end", 0),
                    code=s.get("code", ""),
                    kind=s.get("kind", ""),
                )
                for s in final_state.get("suspicious_snippets", [])
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


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_issue(req: AnalyzeRequest, use_agent: bool = True) -> AnalyzeResponse:
    """Analyze a GitHub Issue — fetches issue content then runs analysis.

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


@router.post("/analyze-error", response_model=AnalyzeResponse)
async def analyze_error(req: AnalyzeErrorRequest) -> AnalyzeResponse:
    """Analyze raw error text — no GitHub Issue needed.

    Paste your traceback, error message, or bug description directly.
    The first line is used as the issue title for retrieval purposes.
    """
    issue = make_synthetic_issue(req.error_text, req.repo_url)
    return await _run_pipeline(issue, req.repo_url)
