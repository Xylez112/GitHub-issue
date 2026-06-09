# GitHub Issue Code Analyzer

输入 GitHub Issue 链接或报错文本 → 自动克隆仓库 → 混合检索相关代码 → Multi-Agent 协作分析 → SSE 实时反馈 → 输出修复建议。

## 核心能力

| 阶段 | 做什么 | 怎么做的 |
|------|--------|---------|
| **解析** | 把 Issue 和代码结构化 | GitHub API 拉取 Issue + Tree-sitter 解析 Python AST |
| **检索** | 从成千上万行代码里找到相关的几行 | BM25 关键词 + SentenceTransformer 语义 → 混合检索 |
| **分析** | 理解问题 → 定位根因 → 生成修复 | LangGraph 5 节点 Agent 流水线 |
| **反馈** | 用户实时看到 Agent 在干什么 | SSE 流式推送 → Vue 3 前端实时展示 |

## 技术栈

| 层 | 技术 |
|----|------|
| **Web 框架** | FastAPI + Pydantic + Uvicorn |
| **Agent 引擎** | LangGraph（5 节点流水线） |
| **代码解析** | Tree-sitter Python AST |
| **向量检索** | SentenceTransformer + ChromaDB |
| **关键词检索** | BM25（rank-bm25） |
| **LLM** | DeepSeek / Claude API（OpenAI 兼容） |
| **流式推送** | SSE（Server-Sent Events） |
| **前端** | Vue 3（Composition API）+ Vite |
| **Git 操作** | GitPython |

## 架构

```
用户输入 Issue URL + Repo URL
              │
              ▼
    ┌──────────────────┐
    │  github.py       │  拉取 Issue + 克隆仓库
    └──────┬───────────┘
           ▼
    ┌──────────────────┐
    │  code_parser.py  │  Tree-sitter 解析所有 .py 文件
    └──────┬───────────┘
           ▼
    ┌──────────────────┐
    │  embedder.py     │  SentenceTransformer 向量化 → ChromaDB
    │  bm25.py         │  BM25 索引
    └──────┬───────────┘
           ▼
    ┌──────────────────┐
    │  retriever.py    │  混合检索（BM25 + 向量）→ 去重排序
    └──────┬───────────┘
           ▼
    ┌──────────────────────────────────────────────────┐
    │  LangGraph Agent 流水线                           │
    │                                                  │
    │  IssueAnalyst → CodeExplorer → FixCrafter        │
    │       │              │              │             │
    │       ▼              ▼              ▼             │
    │  理解 Issue     5 轮工具搜索    生成修复方案       │
    │       │         (search_code,        │             │
    │       │          read_file,          ▼             │
    │       │          find_callers)   Reviewer          │
    │       │                          审核修复方案       │
    │       │                              │             │
    │       └──────────┬───────────────────┘             │
    │                  ▼                                 │
    │             Reporter                              │
    │             生成 Markdown 报告                     │
    └──────────────────┬───────────────────────────────┘
                       ▼
              SSE 实时推送到前端
                       │
                       ▼
            ┌──────────────────┐
            │  Vue 3 前端       │  工业终端美学 UI
            │  AgentLog 实时滚屏 │
            │  ReportView 报告展示│
            └──────────────────┘
```

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- DEEPSEEK_API_KEY（或其他 OpenAI 兼容的 API Key）

### 1. 克隆 + 安装

```bash
git clone https://github.com/Xylez112/GitHub-issue.git
cd GitHub-issue/backend
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
```

### 2. 开发模式（前后端分离）

```bash
# 终端 1：后端（端口 8000）
cd backend
uvicorn app.main:app --reload --port 8000

# 终端 2：前端（端口 5173，自动代理 /api → 8000）
cd frontend
npm install
npm run dev
```

浏览器打开 **http://localhost:5173**。改前端代码自动热更新（HMR），改后端代码 uvicorn 自动重载。

### 3. 部署模式（单端口）

```bash
cd frontend && npm run build    # 产出 dist/
cd ../backend
uvicorn app.main:app --port 8000
```

浏览器打开 **http://localhost:8000**，FastAPI 直接挂载前端构建产物。

Swagger 文档：**http://localhost:8000/docs**

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/analyze` | POST | 提交 Issue URL + Repo URL，传统 JSON 响应 |
| `/api/analyze/stream` | POST | 同上，SSE 流式响应（实时推送 Agent 进度） |
| `/api/analyze-error` | POST | 提交报错文本 + Repo URL |
| `/health` | GET | 健康检查 |

### 请求示例

```json
{
  "issue_url": "https://github.com/fastapi/fastapi/issues/14484",
  "repo_url": "https://github.com/fastapi/fastapi"
}
```

## 项目结构

```
GitHub-Issue/
├── README.md
├── frontend/
│   ├── index.html                 ← Vite 入口
│   ├── index.html.backup          ← 旧版单文件前端（备份）
│   ├── package.json
│   ├── vite.config.js             ← Vite 配置 + /api 代理
│   └── src/
│       ├── main.js                ← Vue 应用挂载
│       ├── App.vue                ← 根组件
│       ├── composables/
│       │   └── useAnalyzer.js     ← 核心状态 + SSE 逻辑
│       ├── components/
│       │   ├── AppHeader.vue      ← 头部
│       │   ├── AppFooter.vue      ← 技术栈标签
│       │   ├── TabSwitch.vue      ← Issue/报错 切换
│       │   ├── IssueForm.vue      ← 表单 + 校验 + 提交
│       │   ├── AgentLog.vue       ← Agent 进度实时滚屏
│       │   ├── ErrorBox.vue       ← 错误提示
│       │   ├── ResultsPanel.vue   ← 结果容器
│       │   ├── SummaryBar.vue     ← 统计面板
│       │   ├── SnippetList.vue    ← 代码片段列表
│       │   ├── FixCard.vue        ← 修复建议卡片
│       │   └── ReportView.vue     ← Markdown 报告
│       └── styles/
│           ├── variables.css      ← 设计变量
│           ├── base.css           ← 全局重置 + 噪点 + 扫描线
│           ├── animations.css     ← 所有 @keyframes
│           └── components.css     ← 共享组件类
└── backend/
    ├── requirements.txt
    ├── .env.example
    ├── app/
    │   ├── main.py                ← FastAPI 入口 + 部署模式挂载
    │   ├── api/routes.py          ← API 路由（含 SSE 端点）
    │   ├── core/config.py         ← Pydantic Settings
    │   ├── models/schemas.py      ← 请求/响应模型
    │   ├── services/
    │   │   ├── github.py          ← Issue 拉取 + Repo 克隆
    │   │   ├── code_parser.py     ← Tree-sitter AST 解析
    │   │   ├── embedder.py        ← Embedding + ChromaDB
    │   │   ├── bm25.py            ← BM25 关键词检索
    │   │   ├── retriever.py       ← 混合检索 + 去重
    │   │   └── analyzer.py        ← LLM 分析（兼容旧路径）
    │   └── graph/
    │       ├── state.py           ← LangGraph 状态定义
    │       ├── builder.py         ← 图构建 + 条件路由
    │       ├── nodes/
    │       │   ├── issue_analyst.py  ← Issue 分析节点
    │       │   ├── code_explorer.py  ← 5 轮 Agent Loop + 工具调度
    │       │   ├── fix_crafter.py    ← 修复方案生成
    │       │   ├── reviewer.py       ← 审核节点
    │       │   └── reporter.py       ← Markdown 报告生成
    │       └── tools/
    │           ├── code_search.py    ← 代码搜索工具
    │           └── file_ops.py       ← 文件读写工具
    ├── eval/
    │   ├── metrics.py             ← MRR / Recall@k
    │   ├── test_cases.json        ← 手工标注测试用例
    │   └── evaluate.py            ← 评估脚本
    └── tests/
        └── test_api.py            ← API 集成测试

## 限制

- 仅支持 Python 仓库
- 分析质量受 LLM 模型影响
- 首次分析需克隆仓库（较大仓库可能较慢）

