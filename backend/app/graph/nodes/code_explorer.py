"""Code Explorer — 在代码库里搜索、读文件、追踪调用链，定位 Bug 根因。

Agent Loop 模式 (ReAct = Reasoning + Acting)：
  1. LLM 收到任务 + 工具列表
  2. LLM 决定调用哪个工具（或输出分析结论）
  3. 执行工具，结果返回给 LLM
  4. 重复步骤 2-3，直到 LLM 认为搜够了（或达到轮次上限）

关键设计决定：最终 State 更新由 _parse_explorer_output() 确定性完成，
不是由 LLM 直接输出 State dict——LLM 不可靠，解析函数可靠。

config 参数：
  LangGraph 的 RunnableConfig 通过 graph.ainvoke(state, config={...}) 传入。
  这里用它传递 collection_name 和 snippets_raw（给工具层用的元数据）。
"""

import json
import re

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI

from ...core.config import settings, setup_logging
from ..state import AnalysisState
from ..tools import search_code, read_file, find_callers, find_callees

logger = setup_logging(__name__)

MAX_ROUNDS = 5  # 每个 Explorer 会话最多 5 轮思考-行动

EXPLORER_SYSTEM = """You are an expert code explorer and bug hunter. Your job is to find the code
most likely causing a reported issue.

## Your Process
1. Start by searching the codebase with keywords from the issue analysis
2. Read promising files fully to understand their context
3. Trace call chains (find_callers, find_callees) to map the bug's path through the code
4. Once you've identified 1-5 files that clearly relate to the issue, describe them and stop

## Stop Conditions
- Stop when you have found code that clearly explains the bug
- If after 3 rounds of searching you find nothing, say so — don't make up matches

## Output Format (at the END of your investigation)
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

Set explored_enough to false only if you need another round of searching.
"""


def _execute_tool(tool_name: str, tool_args: dict, tool_context: dict) -> str:
    """工具分发器——根据 LLM 要求的工具名，调用对应的 Python 函数。

    为什么需要这个分发器？
    LLM 返回的是工具名（字符串 "search_code"）和参数（dict {"query": "..."}），
    不是 Python 函数调用。我们需要手动把字符串映射到实际函数并调用。

    每个工具用 .invoke({...}) 调用——这是 LangChain Tool 的标准方式。
    参数名必须和工具函数的签名一致，否则 LangChain 会报错。
    """
    repo_path = tool_context["repo_path"]
    collection_name = tool_context["collection_name"]
    snippets_raw = tool_context.get("snippets_raw", [])

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
                "snippets_raw": json.dumps(snippets_raw) if isinstance(snippets_raw, list) else str(snippets_raw),
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

    从最后往前找——最近一次包含 "explored_enough" 的 JSON 块
    就是 LLM 的最终结论。靠前的可能是"我还在调查中"的中间输出。
    """
    explored_enough = False
    findings = []

    for msg in reversed(messages):
        if not isinstance(msg, AIMessage):
            continue

        content = str(msg.content)
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

    这是整个系统最核心的节点——它把 Issue Analyst 的关键词
    转化为实际的代码搜索结果，并为后续的 Fix Crafter 提供"原材料"。

    config["configurable"] 包含：
      - collection_name: ChromaDB 集合名
      - snippets_raw: 原始 CodeSnippet 列表（给 find_callers 用的）
    """
    keywords = state.get("keywords", [])
    error_context = state.get("error_context", "")
    repo_path = state.get("repo_path", "")
    rounds = state.get("explore_rounds", 0) + 1

    # 从 config 中提取工具层需要的元数据
    collection_name = ""
    snippets_raw = []
    if config and "configurable" in config:
        collection_name = config["configurable"].get("collection_name", "")
        snippets_raw = config["configurable"].get("snippets_raw", [])

    logger.info("Explorer: round %d, keywords=%s", rounds, keywords)

    # 绑定工具——LLM 现在知道它可以调用这 4 个函数
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=settings.deepseek_api_key,
        base_url="https://api.deepseek.com",
        temperature=0.1,
    ).bind_tools([search_code, read_file, find_callers, find_callees])

    # 构建初始消息
    user_prompt = f"""## Issue Context
{error_context}

## Search Keywords
{', '.join(keywords)}

## Repository Location
{repo_path}

Start by searching for code related to the keywords, then read suspicious files
and trace call chains as needed. Find the root cause code and report your findings."""

    messages = [
        SystemMessage(content=EXPLORER_SYSTEM),
        HumanMessage(content=user_prompt),
    ]

    # ═══════ Agent Loop ═══════
    for round_num in range(MAX_ROUNDS):
        response = llm.invoke(messages)
        messages.append(response)

        # 没有工具调用 → LLM 认为任务完成
        if not response.tool_calls:
            logger.info("Explorer: stopped at round %d (no tool calls)", round_num + 1)
            break

        # 执行 LLM 要求的每个工具
        for tc in response.tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            logger.debug("Explorer: round %d calling %s(%s)", round_num + 1, tool_name, tool_args)

            result = _execute_tool(tool_name, tool_args, {
                "repo_path": repo_path,
                "collection_name": collection_name,
                "snippets_raw": snippets_raw,
            })

            messages.append(ToolMessage(
                content=str(result),
                tool_call_id=tc["id"],
            ))

    # ═══════ 解析最终结论 ═══════
    parsed = _parse_explorer_output(messages)
    explored_enough = parsed["explored_enough"]
    findings = parsed["findings"]

    logger.info(
        "Explorer: explored_enough=%s, findings=%d",
        explored_enough, len(findings),
    )

    # 转成 State 格式
    suspicious = []
    for f in findings:
        suspicious.append({
            "file_path": f.get("file_path", ""),
            "name": f.get("name", ""),
            "line_start": 0,
            "line_end": 0,
            "code": "",
            "kind": "",
            "reason": f.get("reason", ""),
            "relevance_score": 0.0,
        })

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
