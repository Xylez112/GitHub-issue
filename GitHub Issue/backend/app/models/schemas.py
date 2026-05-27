from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    issue_url: str = Field(
        description="GitHub Issue URL, e.g. https://github.com/owner/repo/issues/123"
    )
    repo_url: str = Field(
        description="Repository URL to clone and analyze, e.g. https://github.com/owner/repo"
    )


class AnalyzeErrorRequest(BaseModel):
    error_text: str = Field(
        description="Raw error message, traceback, or bug description — anything you'd paste from terminal"
    )
    repo_url: str = Field(
        description="Repository URL to clone and analyze, e.g. https://github.com/owner/repo"
    )


class CodeSnippet(BaseModel):
    file_path: str
    name: str  # function/class/method name
    line_start: int
    line_end: int
    code: str
    kind: str  # "function", "class", "method"


class FixSuggestion(BaseModel):
    file_path: str
    name: str
    line_start: int
    line_end: int
    issue_summary: str
    suggested_fix: str
    confidence: str  # "high", "medium", "low"


class AnalyzeResponse(BaseModel):
    issue_title: str
    issue_summary: str
    total_files_analyzed: int
    total_snippets_indexed: int
    relevant_snippets: list[CodeSnippet]
    fix_suggestions: list[FixSuggestion]
    raw_analysis: str  # full LLM response for debugging
