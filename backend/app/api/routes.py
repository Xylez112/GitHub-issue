import uuid
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..core.config import setup_logging
from ..models.schemas import AnalyzeRequest, AnalyzeErrorRequest, AnalyzeResponse
from ..services.github import fetch_issue, make_synthetic_issue, clone_repo
from ..services.code_parser import parse_repo
from ..services.embedder import index_snippets, delete_collection
from ..services.retriever import retrieve
from ..services.analyzer import analyze

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


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_issue(req: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze a GitHub Issue — fetches issue content then runs the full pipeline."""
    try:
        issue = await fetch_issue(req.issue_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch issue: {e}")

    return await _run_pipeline(issue, req.repo_url)


@router.post("/analyze-error", response_model=AnalyzeResponse)
async def analyze_error(req: AnalyzeErrorRequest) -> AnalyzeResponse:
    """Analyze raw error text — no GitHub Issue needed.

    Paste your traceback, error message, or bug description directly.
    The first line is used as the issue title for retrieval purposes.
    """
    issue = make_synthetic_issue(req.error_text, req.repo_url)
    return await _run_pipeline(issue, req.repo_url)
