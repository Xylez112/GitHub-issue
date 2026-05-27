# GitHub Issue Code Analyzer

输入 GitHub Issue 链接或报错文本 → 自动克隆仓库 → 检索相关代码 → LLM 输出修复建议。

## 效果

| 指标 | 分数 |
|------|------|
| MRR | 1.000 |
| Recall@5 | 0.833 |
| Recall@20 | 1.000 |

*3 个测试用例，覆盖 FastAPI / Requests / Flask 三个仓库。*

## 工作原理

```
Issue URL / Error Text
       │
       ▼
  github.py          ── 拉取 Issue 内容
       │
       ▼
  code_parser.py     ── AST 解析（函数 / 类 / 方法 / 模块）
       │
       ▼
  embedder.py        ── SentenceTransformer 向量化 → ChromaDB
       │
       ▼
  retriever.py       ── 文本清洗 + 多查询检索 + 去重
       │
       ▼
  analyzer.py        ── DeepSeek LLM 综合分析
       │
       ▼
  修复建议 + 相关代码片段
```

## 快速开始

```bash
# 1. 克隆项目
git clone <repo-url> && cd GitHub-Issue/backend

# 2. 安装依赖（Python 3.12+）
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY（必填）和 GITHUB_TOKEN（可选）

# 4. 启动
uvicorn app.main:app --port 8000

# 5. 打开浏览器
# 前端页面: http://localhost:8000/
# Swagger:  http://localhost:8000/docs
```

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/analyze` | POST | 提交 Issue URL + Repo URL 进行分析 |
| `/api/analyze-error` | POST | 提交报错文本 + Repo URL 进行分析 |
| `/health` | GET | 健康检查 |

### 请求示例

```json
{
  "issue_url": "https://github.com/fastapi/fastapi/issues/14484",
  "repo_url": "https://github.com/fastapi/fastapi"
}
```

### 响应示例

```json
{
  "issue_title": "...",
  "issue_summary": "分析摘要...",
  "total_files_analyzed": 70,
  "total_snippets_indexed": 638,
  "relevant_snippets": [
    {
      "file_path": "fastapi/dependencies/utils.py",
      "name": "get_typed_annotation",
      "kind": "function",
      "line_start": 240,
      "line_end": 280,
      "code": "def get_typed_annotation(...)..."
    }
  ],
  "fix_suggestions": [
    {
      "file_path": "fastapi/dependencies/utils.py",
      "name": "get_typed_annotation",
      "issue_summary": "TYPE_CHECKING annotations break signature resolution",
      "suggested_fix": "...",
      "confidence": "high"
    }
  ],
  "raw_analysis": "..."
}
```

## 评估

```bash
cd backend
# 确保服务已启动在 localhost:8000
python -m eval.evaluate
```

输出 MRR、Recall@5、Recall@10、Recall@20 及每个测试用例的命中详情。

测试用例位于 `backend/eval/test_cases.json`，可自行添加。

## 技术栈

| 层 | 技术 |
|----|------|
| Web 框架 | FastAPI + Pydantic + Uvicorn |
| 代码解析 | Python AST (tree-sitter ready) |
| Embedding | SentenceTransformer (all-MiniLM-L6-v2) |
| 向量数据库 | ChromaDB |
| LLM | DeepSeek (OpenAI-compatible) |
| 评估 | MRR / Recall@k（手工标注） |

## 项目结构

```
GitHub-Issue/
├── README.md
├── frontend/
│   └── index.html              ← 前端页面
└── backend/
    ├── requirements.txt
    ├── .env.example
    ├── app/
    │   ├── main.py              ← FastAPI 入口
    │   ├── api/routes.py        ← API 路由
    │   ├── core/config.py       ← 环境变量
    │   ├── models/schemas.py    ← 数据模型
    │   └── services/
    │       ├── github.py        ← Issue 拉取 + Repo 克隆
    │       ├── code_parser.py   ← AST 代码解析
    │       ├── embedder.py      ← Embedding + ChromaDB
    │       ├── retriever.py     ← 多查询检索 + 去重
    │       └── analyzer.py      ← LLM 分析
    ├── eval/
    │   ├── metrics.py           ← MRR / Recall@k
    │   ├── test_cases.json      ← 标注测试用例
    │   └── evaluate.py          ← 评估脚本
    └── tests/
        └── test_api.py          ← API 集成测试
```

## 限制

- 仅支持 Python 仓库
- 单文件内定位（不追踪跨文件调用链）
- 分析质量受 LLM 模型影响
