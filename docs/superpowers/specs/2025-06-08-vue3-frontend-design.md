# Vue 3 前端工程化设计 Spec

> **Status**: Approved — 2025-06-08
> **From**: 单文件 HTML (808行) → Vue 3 + Vite 工程化前端
> **Dependencies**: Multi-Agent LangGraph 升级已完成

---

## 1. 决策记录

| 决策点 | 选项 |
|--------|------|
| 前后端配合 | C. Vite dev proxy 开发 + FastAPI StaticFiles 挂载 dist 部署 |
| 状态管理 | A. 单一 `useAnalyzer` composable（reactive 对象） |
| CSS 策略 | 全局 styles/ 保留设计 token + 组件 scoped CSS |
| UI 风格 | 完整保留工业终端美学（扫描线、噪点、粗野按钮、交错淡入） |

## 2. 组件树

```
App.vue
├── AppHeader.vue          — ASCII badge + 标题 + 副标题
├── AppFooter.vue          — 技术栈标签
├── TabSwitch.vue          — [1] GitHub Issue / [2] 报错文本
├── IssueForm.vue          — 输入表单 + STREAM 开关 + 提交按钮
├── AgentLog.vue           — SSE 流式进度（实时滚动日志）
├── ResultsPanel.vue       — 结果区域容器（非流式模式用）
│   ├── SummaryBar.vue     — 统计数字
│   ├── SnippetList.vue    — 可疑代码片段列表（可折叠、可 copy）
│   ├── FixCard.vue        — 单个修复方案卡片
│   └── ReportView.vue     — Markdown 报告全文渲染
└── ErrorBox.vue           — 错误提示条
```

## 3. 数据流

单一 `useAnalyzer()` composable 管理所有状态：

```
useAnalyzer()
  state:
    mode: "issue" | "error"
    streamMode: boolean
    loading: boolean
    error: string | null
    logs: Array<{agent, message, isError}>
    summary: {files, indexed, hits, fixes}
    snippets: CodeSnippet[]
    fixDrafts: FixDraft[]
    report: string

  actions:
    submitIssue(url, repo)   → SSE 流式分析
    submitError(text, repo)  → 传统 POST 分析
    reset()
```

组件通过调用 `useAnalyzer()` 获取同一份响应式状态（Vue 的 composable 天生单例模式）。

## 4. CSS 迁移策略

完整保留现有设计 token：

```
frontend/src/styles/
├── variables.css      ← --bg, --surface, --border, --text, --muted, --accent, --teal, --red, --shadow, --radius, --font-ui, --font-display
├── base.css           ← body reset, ::before/::after (噪点+扫描线), scrollbar, ::selection
├── animations.css     ← @keyframes fadeInUp, fadeIn, shimmer, blink, scanlines, grain, borderGlow
└── components.css     ← .card, .field, .snippet, .fix-card, .btn-row（共享组件样式）
```

- `variables.css` + `base.css` + `animations.css` 在 `main.js` 中全局引入
- 组件专属样式用 `<style scoped>` 在 `.vue` 文件中

## 5. SSE 流式接收（Vue 响应式版）

```javascript
// composables/useAnalyzer.js — 核心
async function submitIssue(issueUrl, repoUrl) {
  reset()
  state.loading = true

  const response = await fetch('/api/analyze/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ issue_url: issueUrl, repo_url: repoUrl }),
  })

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop()

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const data = JSON.parse(line.slice(6))

      if (data.type === 'agent_step') {
        state.logs.push({ agent: data.agent, message: data.message, isError: false })
      } else if (data.type === 'result') {
        state.report = data.final_report
      } else if (data.type === 'error') {
        state.logs.push({ agent: 'system', message: data.message, isError: true })
      } else if (data.type === 'done') {
        break
      }
    }
  }

  state.loading = false
}
```

## 6. 文件结构

```
frontend/
├── index.html              ← Vite 入口（<div id="app">）
├── package.json
├── vite.config.js
├── src/
│   ├── main.js
│   ├── App.vue
│   ├── composables/
│   │   └── useAnalyzer.js
│   ├── components/
│   │   ├── AppHeader.vue
│   │   ├── AppFooter.vue
│   │   ├── TabSwitch.vue
│   │   ├── IssueForm.vue
│   │   ├── AgentLog.vue
│   │   ├── ErrorBox.vue
│   │   ├── ResultsPanel.vue
│   │   ├── SummaryBar.vue
│   │   ├── SnippetList.vue
│   │   ├── FixCard.vue
│   │   └── ReportView.vue
│   └── styles/
│       ├── variables.css
│       ├── base.css
│       ├── animations.css
│       └── components.css
└── .gitignore              ← node_modules/, dist/
```

## 7. vite.config.js 代理配置

```js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
```

## 8. 实施顺序

| 步骤 | 内容 | 难度 |
|------|------|------|
| **Step 1** | `npm create vue@latest` 脚手架 + 清理模板 | ⭐ |
| **Step 2** | 迁移 CSS — variables.css / base.css / animations.css | ⭐⭐ |
| **Step 3** | 写 `useAnalyzer` composable（状态 + SSE） | ⭐⭐⭐ |
| **Step 4** | 拆 AppHeader + AppFooter + TabSwitch | ⭐ |
| **Step 5** | 拆 IssueForm（表单 + 校验 + 模式切换） | ⭐⭐ |
| **Step 6** | 拆 AgentLog + ErrorBox | ⭐ |
| **Step 7** | 拆 ResultsPanel + SummaryBar + SnippetList + FixCard + ReportView | ⭐⭐ |
| **Step 8** | 组装 App.vue + 端到端调试 | ⭐⭐ |
| **Step 9** | FastAPI 挂载 dist/ + 部署验证 | ⭐ |

## 9. 风险

| 风险 | 缓解 |
|------|------|
| 现有 CSS 迁移时样式丢失 | 逐步迁移——先全局 CSS 全部搬过去，确认视觉一致后再拆到组件 scoped |
| Vite proxy 配置 CORS 问题 | FastAPI 已配置 `allow_origins=["*"]`，无需额外处理 |
| Vue 响应式 + ReadableStream 异步兼容 | `ref.push()` / `reactive` 原生支持异步更新，无需额外处理 |
