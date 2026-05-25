import ast
from pathlib import Path

from ..models.schemas import CodeSnippet

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".tox", ".eggs", "build", "dist", "test", "tests",
    "migrations", ".github", "docs_src", "examples", "samples",
}
MAX_FILE_BYTES = 500_000  # skip files larger than 500KB


def parse_repo(repo_path: Path) -> list[CodeSnippet]:
    snippets: list[CodeSnippet] = []

    for py_file in repo_path.rglob("*.py"):
        if any(d in py_file.parts for d in SKIP_DIRS):
            continue
        if py_file.stat().st_size > MAX_FILE_BYTES:
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        rel_path = str(py_file.relative_to(repo_path))
        file_snippets = _extract_definitions(source, rel_path)
        snippets.extend(file_snippets)
        
        if source.strip():
            snippets.append(CodeSnippet(
                file_path=rel_path,
                name=py_file.stem,
                line_start=1,
                line_end=len(source.splitlines()) if source else 1,
                code=source,
                kind="module",
            ))

    return snippets


def _get_source_lines(source: str, start: int, end: int) -> str:
    """Extract source code lines from 1-based line numbers."""
    lines = source.splitlines()
    return "\n".join(lines[start - 1:end])


def _get_docstring(node: ast.AST) -> str | None:
    return ast.get_docstring(node)


def _extract_definitions(source: str, rel_path: str) -> list[CodeSnippet]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    snippets: list[CodeSnippet] = []
    lines = source.splitlines()
    
    def _iter_body(body: list[ast.stmt], class_name: str | None = None):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "method" if class_name else "function"
                name = f"{class_name}.{node.name}" if class_name else node.name
                snippets.append(CodeSnippet(
                    file_path=rel_path,
                    name=name,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    code="\n".join(lines[node.lineno - 1:node.end_lineno or node.lineno]),
                    kind=kind,
                ))

            elif isinstance(node, ast.ClassDef):
                snippets.append(CodeSnippet(
                    file_path=rel_path,
                    name=node.name,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    code="\n".join(lines[node.lineno - 1:node.end_lineno or node.lineno]),
                    kind="class",
                ))
                _iter_body(node.body, class_name=node.name)

    _iter_body(tree.body)
    return snippets
