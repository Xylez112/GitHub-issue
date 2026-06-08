"""文件操作工具 —— read_file, find_callers, find_callees。

给 LLM 用的两类工具：
  1. read_file —— 读文件内容（带行号，截断长文件）
  2. find_callers / find_callees —— 追踪调用关系（正则匹配，非完整 AST 分析）

设计原则：
  - 所有工具返回纯文本——LLM 只能读文本
  - 大文件自动截断——防止上下文窗口爆炸
  - 错误不抛异常——返回错误字符串，让 LLM 知道出了什么事
"""

import json
import re
from pathlib import Path

from langchain_core.tools import tool


@tool
def read_file(repo_path: str, file_path: str, start_line: int = 1, end_line: int | None = None) -> str:
    """Read a file from the cloned repository with line numbers.

    Use this tool when:
    - You found a suspicious file via search_code and want to see its full context
    - You need to understand imports or surrounding functions
    - You want to see what other functions exist in the same file

    Args:
        repo_path: Root path of the cloned repository (provided by the system)
        file_path: Relative path to the file (e.g. "src/services/user.py")
        start_line: First line to read (1-based, default 1)
        end_line: Last line to read (inclusive). If omitted, reads to end of file.

    Returns:
        File content with line numbers (format: "LINE| code")
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

    # Clamp to valid range（防止 LLM 传越界的行号）
    start_line = max(1, min(start_line, len(lines)))
    end_line = max(start_line, min(end_line, len(lines)))

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
    - You want to understand what code passes data to the broken function

    Args:
        repo_path: Root path of the cloned repository (provided by system)
        snippets_raw: JSON string of all CodeSnippet objects in the repo (provided by system)
        func_name: Name of the function to find callers for (e.g. "create_user")
        file_path: Optional filter — only search in this file

    Returns:
        List of callers with file paths and line numbers
    """
    try:
        snippets_data = json.loads(snippets_raw)
    except (json.JSONDecodeError, TypeError):
        return "Error: snippets_raw is not valid JSON — the system should provide this"

    # 在所有 snippet 代码中搜索对 func_name 的调用
    # 匹配模式：func_name( —— 这是"函数调用"的文本特征
    callers = []
    pattern = re.compile(rf"\b{re.escape(func_name)}\s*\(")

    for s_dict in snippets_data:
        if file_path and s_dict["file_path"] != file_path:
            continue

        code = s_dict.get("code", "")
        if pattern.search(code):
            callers.append({
                "file_path": s_dict["file_path"],
                "name": s_dict["name"],
                "kind": s_dict.get("kind", ""),
                "line_start": s_dict["line_start"],
            })

    if not callers:
        return f"No callers found for `{func_name}`"
    if len(callers) > 20:
        return f"Found {len(callers)} callers (too many, showing first 20):\n" + \
               "\n".join(
                   f"- `{c['name']}` ({c['kind']}) in {c['file_path']}:{c['line_start']}"
                   for c in callers[:20]
               )

    return "Callers of `" + func_name + "`:\n" + \
           "\n".join(
               f"- `{c['name']}` ({c['kind']}) in {c['file_path']}:{c['line_start']}"
               for c in callers
           )


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
        repo_path: Root path of the cloned repository (provided by system)
        file_path: Relative path to the file containing the function
        func_name: Name of the function to analyze

    Returns:
        List of functions called by func_name
    """
    full_path = Path(repo_path) / file_path
    if not full_path.exists():
        return f"Error: File not found: {file_path}"

    try:
        source = full_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Error: Cannot read {file_path}"

    lines = source.splitlines()

    # 找到目标函数的代码范围（通过缩进级别判断函数边界）
    in_func = False
    func_lines = []
    indent_level = 0

    for i, line in enumerate(lines):
        if f"def {func_name}(" in line or f"async def {func_name}(" in line:
            in_func = True
            indent_level = len(line) - len(line.lstrip())
            continue

        if in_func:
            current_indent = len(line) - len(line.lstrip())
            # 遇到同级或更靠左的非空行 = 函数结束
            if line.strip() and current_indent <= indent_level:
                break
            func_lines.append(line)

    if not func_lines:
        return f"Function `{func_name}` not found in {file_path}"

    # 提取函数调用：匹配 word_name(...)
    func_code = "\n".join(func_lines)
    calls = re.findall(r"(\w+)\s*\(", func_code)

    # 过滤 Python 关键字和内置函数——这些不是"真正的调用者"
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
