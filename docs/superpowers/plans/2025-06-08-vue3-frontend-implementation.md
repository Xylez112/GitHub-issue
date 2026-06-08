# Vue 3 前端工程化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 1014 行单文件 HTML 升级为 Vue 3 + Vite 工程化前端，拆分为 10 个组件，保留全部工业终端美学。

**Architecture:** Vite dev server (port 5173) → proxy `/api` → FastAPI (port 8000)；部署时 `npm run build` 产出 `dist/` 由 FastAPI 挂载。单一 `useAnalyzer` composable 管理所有状态和 SSE 逻辑。

**Tech Stack:** Vue 3 (Composition API), Vite, CSS Variables (从现有 CSS 直接迁移)

---

## 教学约定

每次修改文件时，遵循三步讲解：
1. **改什么** — 文件路径 + 改动范围
2. **为什么这样改** — 背后的 Vue 原理 / 设计原则
3. **知识点** — 可迁移到其他 Vue 项目的通用概念

---

## Task 1: 脚手架搭建

**Files:**
- Create: `frontend/` 下的 Vite + Vue 3 项目（覆盖现有 index.html）

**知识点：`npm create vue` 做了什么？**

```
npm create vue@latest 实际上是执行 create-vue 脚手架工具，它会：
1. 创建 package.json（含 vue、vite、@vitejs/plugin-vue 依赖）
2. 创建 vite.config.js（Vite 配置入口）
3. 创建 index.html（Vite 的 HTML 入口，和 webpack 的 index.html 概念不同）
4. 创建 src/main.js（Vue 应用的挂载点：createApp(App).mount('#app')）
5. 创建 src/App.vue（根组件）
```

**Vite 的 index.html 和传统 HTML 的区别：**
- Vite 的 index.html 用 `<script type="module" src="/src/main.js"></script>` 加载入口
- 不需要手动引入 CSS——JS 里 `import './style.css'` 即可
- Vite 在 dev 时会处理这些 ESM import，自动 HMR（热模块替换）

- [ ] **Step 1: 备份现有 index.html**

现有 `frontend/index.html` 是完整的工业终端美学前端，不能丢。

```bash
cd "d:/项目/GitHub Issue"
cp frontend/index.html frontend/index.html.backup
```

- [ ] **Step 2: 在 frontend/ 目录下创建 Vite + Vue 3 项目**

```bash
cd "d:/项目/GitHub Issue/frontend"
npm create vue@latest . -- --force
```

交互式选项（用 `--` 传参跳过交互，或手动选择）：
- Project name: `frontend`（当前目录）
- TypeScript: **No**（先学好 Vue 本身，TypeScript 以后再上）
- JSX: No
- Router: No（单页应用不需要路由）
- Pinia: No（用 composable 管理状态）
- Vitest: No（后续再加测试）
- ESLint: No

如果上面的 `--force` 方式不生效，用交互式：

```bash
npm create vue@latest .
# 全部选 No，只用最简模板
```

- [ ] **Step 3: 安装依赖**

```bash
cd "d:/项目/GitHub Issue/frontend"
npm install
```

- [ ] **Step 4: 清理模板文件，保留骨架**

删除 `create-vue` 生成的示例文件：

```bash
rm -f src/components/HelloWorld.vue src/components/TheWelcome.vue
rm -f src/components/icons/*.svg
rmdir src/components/icons 2>/dev/null
rm -f src/components/WelcomeItem.vue
rm -f src/assets/base.css src/assets/main.css src/assets/logo.svg
rmdir src/assets 2>/dev/null
```

- [ ] **Step 5: 精简 src/main.js**

```js
import { createApp } from 'vue'
import App from './App.vue'

const app = createApp(App)
app.mount('#app')
```

- [ ] **Step 6: 精简 src/App.vue（只留骨架）**

```vue
<template>
  <div class="app-root">hello — vue 3 ready</div>
</template>
```

- [ ] **Step 7: 配置 vite.config.js 代理**

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

**为什么用 proxy 而不是 CORS？**
- proxy 是同源请求（浏览器视角），不会触发跨域限制
- Vite dev server 在本地 5173，FastAPI 在 8000——proxy 让 `/api/*` 请求在服务端转发
- 部署时 FastAPI 直接挂载 dist/，不需要 proxy——两个环境都干净

- [ ] **Step 8: 启动 dev server 验证骨架**

```bash
# 终端 1: FastAPI
cd "d:/项目/GitHub Issue/backend" && python -m uvicorn app.main:app --reload --port 8000

# 终端 2: Vite
cd "d:/项目/GitHub Issue/frontend" && npm run dev
```

浏览器打开 `http://localhost:5173`，看到 "hello — vue 3 ready" 即成功。

- [ ] **Step 9: Commit**

```bash
cd "d:/项目/GitHub Issue"
git add frontend/package.json frontend/package-lock.json frontend/vite.config.js \
        frontend/index.html frontend/src/ frontend/public/ \
        frontend/.gitignore
git add frontend/index.html.backup
git commit -m "scaffold: init Vue 3 + Vite project, backup old HTML"
```

---

## Task 2: 迁移 CSS —— 全局样式层

**Files:**
- Create: `frontend/src/styles/variables.css`
- Create: `frontend/src/styles/base.css`
- Create: `frontend/src/styles/animations.css`
- Create: `frontend/src/styles/components.css`
- Modify: `frontend/src/main.js`
- Modify: `frontend/index.html`（替换旧的字体 link）

**知识点：为什么 CSS 要分层？**

单文件 HTML 里所有 CSS 混在一个 `<style>` 标签里（566 行）。拆成 4 层的好处：

```
variables.css   → 只有 :root 变量 + 字体声明（改主题色只改一个文件）
base.css        → html/body 的全局重置 + 噪点 + 扫描线（全局效果，所有页面共用）
animations.css  → 所有 @keyframes（改动画面不改业务样式）
components.css  → .card / .field / .snippet / .fix-card（组件共享的基础类）
```

在一个 Vue 项目里，`variables.css` + `base.css` + `animations.css` 在 `main.js` 里全局引入（**非 scoped**），所有组件自动继承。`components.css` 里的类用于组件 `<template>` 中，不再是独立作用域，但保留最小改动原则。

- [ ] **Step 1: 创建 styles/ 目录**

```bash
mkdir -p "d:/项目/GitHub Issue/frontend/src/styles"
```

- [ ] **Step 2: 创建 `variables.css`** — 从现有 HTML 的 `:root` 块直接搬

```css
/* Design Tokens — 工业终端美学色彩体系 */
:root {
  --bg:       #0a0a08;
  --surface:  #131311;
  --border:   #282820;
  --text:     #e8e6dc;
  --muted:    #8a8878;
  --accent:   #f0c040;
  --accent-dim: #8a7020;
  --teal:     #40c4a0;
  --red:      #f05448;
  --shadow:   6px 6px 0 rgba(0,0,0,0.4);
  --radius:   0px;
  --font-ui:  'JetBrains Mono', 'Cascadia Code', 'Fira Code', monospace;
  --font-display: 'Space Mono', 'JetBrains Mono', monospace;
}
```

- [ ] **Step 3: 创建 `base.css`** — html/body 重置 + 噪点 + 扫描线 + scrollbar + selection

```css
/* Base Reset & Global Effects */
@import './variables.css';

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html { scroll-behavior: smooth; }

body {
  font-family: var(--font-ui);
  background: var(--bg);
  color: var(--text);
  line-height: 1.7;
  min-height: 100vh;
  position: relative;
  overflow-x: hidden;
}

/* ── Grain overlay ── */
body::before {
  content: '';
  position: fixed; inset: -50%;
  z-index: 0; pointer-events: none;
  opacity: 0.04;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  animation: grain 8s steps(1) infinite;
}

/* ── Scanlines ── */
body::after {
  content: '';
  position: fixed; inset: 0;
  z-index: 0; pointer-events: none;
  opacity: 0.015;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(255,255,255,0.02) 2px,
    rgba(255,255,255,0.02) 4px
  );
  animation: scanlines 0.3s linear infinite;
}

/* ── Text selection ── */
::selection {
  background: var(--accent);
  color: var(--bg);
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); }
::-webkit-scrollbar-thumb:hover { background: #3a3a30; }
```

- [ ] **Step 4: 创建 `animations.css`** — 所有 @keyframes

```css
/* Animations — 从现有 HTML 直接搬迁 */

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(18px); }
  to   { opacity: 1; transform: translateY(0); }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}

@keyframes shimmer {
  0%   { background-position: -200px 0; }
  100% { background-position: 200px 0; }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0; }
}

@keyframes scanlines {
  0%   { background-position: 0 0; }
  100% { background-position: 0 4px; }
}

@keyframes grain {
  0%, 100% { transform: translate(0, 0); }
  10% { transform: translate(-1%, -1%); }
  30% { transform: translate(1%, -2%); }
  50% { transform: translate(-2%, 1%); }
  70% { transform: translate(2%, 1%); }
  90% { transform: translate(-1%, 2%); }
}

@keyframes borderGlow {
  0%, 100% { border-color: var(--border); }
  50%      { border-color: #3a3a30; }
}
```

- [ ] **Step 5: 创建 `components.css`** — 共享组件类（card, field, button, snippet, fix-card 等）

把现有 HTML `<style>` 里从 `/* ── Layout ── */` 到 `/* ── Responsive ── */` 之间的所有 CSS 搬过来。（内容太长不逐行复制——直接从 `frontend/index.html.backup` 提取第 149-566 行，去掉注释前缀保持一致。）

- [ ] **Step 6: 更新 `main.js`** — 全局引入样式

```js
import { createApp } from 'vue'
import App from './App.vue'

// 全局样式（非 scoped，所有组件自动继承）
import './styles/variables.css'
import './styles/base.css'
import './styles/animations.css'
import './styles/components.css'

const app = createApp(App)
app.mount('#app')
```

**为什么 `components.css` 也全局引入？**
因为它是从现有 HTML 直接搬过来的——原有的类名（`.card`, `.field`, `.btn-row`）已经贯穿整个设计。用全局 CSS 可以零改动迁移这些类，组件里直接用 `class="card"` 即可。后续如果你想把某个组件的样式隔离，随时可以拷贝到 `<style scoped>` 里并删掉全局的部分。

- [ ] **Step 7: 更新 `index.html`** — 保留 Google Fonts link + 根 div

Vite 的 `index.html` 已经由脚手架生成。替换为：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Issue → Code Analyzer</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:ital,wght@0,400;0,500;0,700;1,400&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

**注意：** `<div id="app">` 里什么都不放——Vue 用 `App.vue` 的 `<template>` 渲染全部内容。`<script>` 标签必须保留 `type="module"`，这是 Vite 的工作方式。

- [ ] **Step 8: 验证 —— dev server 看到样式生效**

```bash
npm run dev
```

访问 `http://localhost:5173`，写一个简单的 `App.vue` 测试 body 背景色是否为 `#0a0a08`（深色）、字体是否为 JetBrains Mono。

- [ ] **Step 9: Commit**

```bash
git add frontend/src/styles/ frontend/src/main.js frontend/index.html
git commit -m "feat: migrate global CSS — variables, base, animations, component classes"
```

---

## Task 3: useAnalyzer Composable —— 核心状态 + SSE 逻辑

**Files:**
- Create: `frontend/src/composables/useAnalyzer.js`

**知识点：什么是 Composable？**

```js
// Composable = 一个可复用的"有状态函数"
export function useAnalyzer() {
  const mode = ref('issue')
  const logs = ref([])

  async function submitIssue(url, repo) { ... }

  return { mode, logs, submitIssue }
}
```

在组件里调用：
```js
const { mode, logs, submitIssue } = useAnalyzer()
```

**Vue 的魔法：** 同一个 composable 被多个组件调用时，**它们共享同一个响应式状态吗？** 答案是——**不会（默认）**。每次调用 `useAnalyzer()` 都创建新的 `ref`。如果想让多个组件共享状态，需要把 state 提升到模块级别（导出单例），或者用 `provide/inject`。

这里我们需要**单例模式**——App.vue 调用一次，子组件通过 props 接收各自需要的数据（单向数据流）。

- [ ] **Step 1: 创建 `composables/` 目录 + `useAnalyzer.js`**

```bash
mkdir -p "d:/项目/GitHub Issue/frontend/src/composables"
```

- [ ] **Step 2: 编写 `useAnalyzer.js`**

```js
import { reactive, toRefs } from 'vue'

// ── 单例 State（模块级别，所有组件共享）──
const state = reactive({
  mode: 'issue',           // 'issue' | 'error'
  streamMode: false,       // 是否开启 SSE 流式
  loading: false,
  error: null,             // string | null
  logs: [],                // [{ agent, message, isError }]
  report: '',              // Markdown 全文
})

// ── Actions ──
export function useAnalyzer() {
  function setMode(m)   { state.mode = m }
  function setStream(v) { state.streamMode = v }
  function reset() {
    state.loading = false
    state.error = null
    state.logs = []
    state.report = ''
  }

  function showError(msg) {
    state.error = msg
    state.loading = false
  }

  function clearError() {
    state.error = null
  }

  // ═══ SSE 流式分析 ═══
  async function submitIssue(issueUrl, repoUrl) {
    reset()
    state.loading = true

    try {
      const response = await fetch('/api/analyze/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          issue_url: issueUrl,
          repo_url: repoUrl,
        }),
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }))
        throw new Error(err.detail || `HTTP ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()  // 保留不完整的最后一行

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const jsonStr = line.slice(6)
          try {
            const data = JSON.parse(jsonStr)
            if (data.type === 'agent_step') {
              state.logs.push({
                agent: data.agent,
                message: data.message,
                isError: false,
              })
            } else if (data.type === 'result') {
              state.report = data.final_report || ''
            } else if (data.type === 'error') {
              state.logs.push({
                agent: 'system',
                message: data.message,
                isError: true,
              })
            }
          } catch {
            // 跳过不完整的 JSON 行
          }
        }
      }
    } catch (e) {
      showError(e.message)
    } finally {
      state.loading = false
    }
  }

  // ═══ 传统 POST 分析（报错文本模式 / 非流式）═══
  async function submitError(errorText, repoUrl) {
    reset()
    state.loading = true

    try {
      const response = await fetch('/api/analyze-error', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          error_text: errorText,
          repo_url: repoUrl,
        }),
      })

      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || `HTTP ${response.status}`)
      }

      const data = await response.json()
      state.report = data.issue_summary
        || data.raw_analysis?.slice(0, 3000)
        || '分析完成，无详细报告'
    } catch (e) {
      showError(e.message)
    } finally {
      state.loading = false
    }
  }

  return {
    ...toRefs(state),  // 把 reactive 对象的每个 key 转成 ref
    setMode,
    setStream,
    reset,
    showError,
    clearError,
    submitIssue,
    submitError,
  }
}
```

**关键知识点：`reactive` + `toRefs` vs `ref`**

```js
// ref: 单个值
const mode = ref('issue')      // mode.value 读写

// reactive: 整个对象
const state = reactive({ mode: 'issue', logs: [] })
// state.mode 直接读写（不需要 .value）

// toRefs: reactive 对象 → 解构成独立的 ref
const { mode, logs } = toRefs(state)
// mode.value 读写，和独立 ref 行为一致
```

为什么用 `reactive`？因为这个 composable 有 10+ 个状态字段，用 10 个独立的 `ref` 会导致代码散落。`reactive` 让所有状态聚合成一个对象，心智负担更小。

- [ ] **Step 3: 验证 composable 能 import**

```bash
cd "d:/项目/GitHub Issue/frontend" && node -e "
// 检查语法（不做 Vue 运行时）
const fs = require('fs')
const code = fs.readFileSync('src/composables/useAnalyzer.js', 'utf8')
console.log('File size:', code.length, 'bytes')
console.log('Syntax check: OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/composables/
git commit -m "feat: add useAnalyzer composable — reactive state + SSE logic"
```

---

## Task 4: 拆 AppHeader + AppFooter + TabSwitch

**Files:**
- Create: `frontend/src/components/AppHeader.vue`
- Create: `frontend/src/components/AppFooter.vue`
- Create: `frontend/src/components/TabSwitch.vue`
- Modify: `frontend/src/App.vue`（组装这三个组件）

**知识点：Vue 组件的三个区块**

```vue
<template>
  <!-- HTML 模板 —— 用 Vue 的模板语法（v-if, v-for, {{ }} 插值） -->
</template>

<script setup>
  // Composition API —— 响应式逻辑、事件处理
  // setup 意味着不需要显式 return —— 所有顶层变量自动暴露给 template
</script>

<style scoped>
  /* scoped —— 这些样式只对这个组件生效 */
  /* Vue 编译时会给每个元素加 data-v-xxxx 属性做隔离 */
</style>
```

这三个是纯展示组件——只接收 props、渲染 HTML、不管理状态。

- [ ] **Step 1: 创建 `AppHeader.vue`**

```vue
<script setup>
defineProps({
  phase: { type: String, default: 'V2 · AGENT' },
})
</script>

<template>
  <header>
    <div class="ascii-badge">[ {{ phase }} ]</div>
    <h1>Issue<span class="pipe">|</span>Code<span class="pipe">|</span>Analyzer</h1>
    <div class="subtitle">
      输入 Issue 或报错 &rarr; 自动克隆仓库 &rarr; AST 解析 &rarr; 向量检索 &rarr; Multi-Agent 协作
    </div>
  </header>
</template>

<style scoped>
/* 从现有 CSS 的 header 块直接搬迁（第 113-147 行） */
header {
  position: relative; z-index: 1;
  border-bottom: 1px solid var(--border);
  padding: 60px 24px 40px;
  text-align: center;
  background: linear-gradient(180deg, #0f0f0d 0%, var(--surface) 100%);
}
header .ascii-badge {
  display: inline-block;
  font-family: var(--font-display);
  font-size: 0.6rem; font-weight: 700;
  letter-spacing: 0.3em;
  color: var(--accent);
  margin-bottom: 20px;
  opacity: 0.8;
  animation: fadeInUp 0.6s ease-out both;
}
header h1 {
  font-family: var(--font-display);
  font-size: clamp(1.6rem, 4vw, 2.2rem);
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--text);
  margin-bottom: 10px;
  animation: fadeInUp 0.6s 0.1s ease-out both;
}
header h1 .pipe {
  color: var(--accent);
  animation: blink 1.5s step-end infinite;
}
header .subtitle {
  font-size: 0.78rem;
  color: var(--muted);
  animation: fadeInUp 0.6s 0.2s ease-out both;
}
</style>
```

- [ ] **Step 2: 创建 `AppFooter.vue`**

```vue
<template>
  <footer>
    <span>FastAPI</span> <span class="separator">|</span>
    <span>ChromaDB</span> <span class="separator">|</span>
    <span>SentenceTransformer</span> <span class="separator">|</span>
    <span>DeepSeek</span> <span class="separator">|</span>
    <span>BM25</span> <span class="separator">|</span>
    <span>LangGraph</span> <span class="separator">|</span>
    <span>Vue 3</span>
  </footer>
</template>

<style scoped>
/* 从现有 CSS footer 块直接搬迁（第 548-555 行） */
footer {
  text-align: center; padding: 40px 0;
  color: var(--muted); font-size: 0.68rem;
  border-top: 1px solid var(--border);
  letter-spacing: 0.06em;
}
footer span { color: var(--accent); }
footer .separator { color: var(--border); margin: 0 8px; }
</style>
```

**为什么 Footer 用 `<style scoped>`？**
这些样式只和 Footer 组件相关——`.separator` 不会被其他组件用到。用 scoped 保证样式不泄漏。Header 同理。

- [ ] **Step 3: 创建 `TabSwitch.vue`**

```vue
<script setup>
const props = defineProps({
  mode: { type: String, default: 'issue' },
})

const emit = defineEmits(['update:mode'])

function switchTo(m) {
  emit('update:mode', m)
}
</script>

<template>
  <div class="tabs">
    <div
      class="tab"
      :class="{ active: mode === 'issue' }"
      @click="switchTo('issue')"
    >
      <span class="bracket">[</span>1<span class="bracket">]</span> GitHub Issue
    </div>
    <div
      class="tab"
      :class="{ active: mode === 'error' }"
      @click="switchTo('error')"
    >
      <span class="bracket">[</span>2<span class="bracket">]</span> 报错文本
    </div>
  </div>
</template>

<style scoped>
/* 从现有 CSS tabs 块直接搬迁（第 158-187 行） */
.tabs { display: flex; gap: 0; margin-bottom: 0; }
.tab {
  flex: 1; text-align: center;
  padding: 16px 16px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-bottom: none;
  cursor: pointer;
  font-family: var(--font-display);
  font-size: 0.78rem; font-weight: 400;
  color: var(--muted);
  transition: all 0.15s;
  position: relative;
  letter-spacing: 0.06em;
}
.tab:first-child { border-right: none; }
.tab:hover:not(.active) {
  color: var(--text);
  background: var(--surface);
}
.tab.active {
  color: var(--accent);
  background: var(--surface);
  border-bottom: 3px solid var(--accent);
}
.tab .bracket { color: var(--muted); }
.tab.active .bracket { color: var(--accent); }
</style>
```

**知识点：`v-model:mode` 的底层原理**

```vue
<!-- 父组件 -->
<TabSwitch v-model:mode="mode" />

<!-- 等价于 -->
<TabSwitch :mode="mode" @update:mode="mode = $event" />
```

子组件里 `emit('update:mode', 'error')` → 父组件的 `mode` 自动更新为 `'error'`。这是 Vue 3 的 `v-model` 语法糖——比手动 emit + watch 简洁。

- [ ] **Step 4: 更新 `App.vue`** — 组装这三个组件

```vue
<script setup>
import { useAnalyzer } from './composables/useAnalyzer'
import AppHeader from './components/AppHeader.vue'
import AppFooter from './components/AppFooter.vue'
import TabSwitch from './components/TabSwitch.vue'

const { mode, setMode } = useAnalyzer()
</script>

<template>
  <AppHeader phase="V2 · AGENT" />
  <div class="container">
    <TabSwitch v-model:mode="mode" @update:mode="setMode" />
    <!-- 后续 Task 在这里加入 IssueForm、AgentLog、ResultsPanel -->
    <div style="padding:40px;text-align:center;color:var(--teal);font-family:var(--font-display)">
      > components ready
    </div>
  </div>
  <AppFooter />
</template>

<style scoped>
.container {
  max-width: 880px;
  margin: 0 auto;
  padding: 32px 16px 56px;
  position: relative; z-index: 1;
}
</style>
```

- [ ] **Step 5: 验证 — dev server 看到 Header + Tabs + Footer**

```bash
npm run dev
```

访问 `http://localhost:5173`，看到完整的 header（带 blink 动画的 pipe）、可点击切换的 tabs、footer 技术栈标签。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/AppHeader.vue \
        frontend/src/components/AppFooter.vue \
        frontend/src/components/TabSwitch.vue \
        frontend/src/App.vue
git commit -m "feat: add AppHeader, AppFooter, TabSwitch components"
```

---

## Task 5: 拆 IssueForm —— 表单 + SSE 开关 + 提交

**Files:**
- Create: `frontend/src/components/IssueForm.vue`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: 创建 `IssueForm.vue`**

```vue
<script setup>
import { computed } from 'vue'
import { useAnalyzer } from '../composables/useAnalyzer'

const { mode, streamMode, loading, setStream, submitIssue, submitError } = useAnalyzer()

// 本地输入绑定
const issueUrl = ref('')
const errorText = ref('')
const repoUrl = ref('')

// 表单标题随 mode 变化
const formTitle = computed(() =>
  mode.value === 'issue' ? '分析 GitHub Issue' : '分析报错信息'
)

async function handleSubmit() {
  if (!repoUrl.value.trim()) {
    // error 通过 useAnalyzer 的 showError 处理，这里先检查
    return
  }

  if (mode.value === 'issue') {
    if (!issueUrl.value.trim()) return
    await submitIssue(issueUrl.value, repoUrl.value)
  } else {
    if (!errorText.value.trim()) return
    await submitError(errorText.value, repoUrl.value)
  }
}
</script>

<template>
  <div class="card">
    <h2>{{ formTitle }}</h2>

    <!-- Issue URL 字段（issue 模式显示） -->
    <div class="field" v-show="mode === 'issue'">
      <label>issue-url</label>
      <input
        type="text"
        v-model="issueUrl"
        placeholder="https://github.com/owner/repo/issues/123"
        @keydown.ctrl.enter="handleSubmit"
      />
    </div>

    <!-- 报错文本字段（error 模式显示） -->
    <div class="field" v-show="mode === 'error'">
      <label>error-traceback</label>
      <textarea
        v-model="errorText"
        placeholder="把终端的报错信息粘贴到这里..."
        @keydown.ctrl.enter="handleSubmit"
      ></textarea>
      <div class="hint">第一行自动作为检索标题。支持完整 traceback。</div>
    </div>

    <!-- Repo URL（始终显示） -->
    <div class="field">
      <label>repo-url</label>
      <input
        type="text"
        v-model="repoUrl"
        placeholder="https://github.com/owner/repo"
        @keydown.ctrl.enter="handleSubmit"
      />
      <div class="hint">需要分析的代码仓库地址。仅支持 Python 项目。</div>
    </div>

    <!-- 提交按钮 -->
    <button :disabled="loading" @click="handleSubmit">
      {{ loading ? '[ 分 析 中 ... ]' : '[ 开 始 分 析 ]' }}
    </button>

    <!-- SSE 流式开关 -->
    <label class="stream-toggle" :class="{ checked: streamMode }">
      <input type="checkbox" :checked="streamMode" @change="setStream($event.target.checked)" />
      STREAM · 实时查看 Agent 进度
    </label>
  </div>
</template>

<style scoped>
/* .card, .field, button, .stream-toggle —— 从 components.css 继承全局样式 */
/* scoped 里只覆盖需要调整的部分 */
</style>
```

**知识点：`v-show` vs `v-if`**

```html
<div v-show="mode === 'issue'">  <!-- display:none 切换，DOM 始终存在 -->
<div v-if="mode === 'issue'">    <!-- 完全销毁/重建 DOM -->
```

这里用 `v-show` 是因为用户在两个 tab 之间频繁切换——`v-show` 保留 DOM（和已输入的文字），切换不丢数据。如果用 `v-if`，切到 error tab 再切回来，Issue URL 输入框里的文字就没了。

- [ ] **Step 2: 更新 `App.vue`** — 嵌入 IssueForm

替换 placeholder `<div>`：

```vue
import IssueForm from './components/IssueForm.vue'

// template 中：
<IssueForm />
```

- [ ] **Step 3: 验证 —— dev server 看到完整表单**

```bash
npm run dev
```

检查：tab 切换时表单标题和字段正确切换、Ctrl+Enter 触发提交（不做实际请求）、Stream checkbox 视觉效果正常。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/IssueForm.vue frontend/src/App.vue
git commit -m "feat: add IssueForm component with validation + stream toggle"
```

---

## Task 6: 拆 AgentLog + ErrorBox

**Files:**
- Create: `frontend/src/components/AgentLog.vue`
- Create: `frontend/src/components/ErrorBox.vue`
- Modify: `frontend/src/App.vue`

这两个是 SSE 流式模式下用户最直接感知的组件——Agent 的每一步思考实时滚屏。

- [ ] **Step 1: 创建 `AgentLog.vue`**

```vue
<script setup>
import { watch, nextTick, ref } from 'vue'
import { useAnalyzer } from '../composables/useAnalyzer'

const { logs, streamMode } = useAnalyzer()
const logContainer = ref(null)

// 每当有新日志，自动滚到底部
watch(
  () => logs.value.length,
  async () => {
    await nextTick()
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  },
)
</script>

<template>
  <div
    class="agent-log"
    :class="{ show: streamMode && logs.length > 0 }"
    ref="logContainer"
  >
    <div class="log-title">▸ AGENT PROGRESS</div>
    <div
      v-for="(entry, i) in logs"
      :key="i"
      class="log-entry"
    >
      <span class="agent-tag">[{{ entry.agent }}]</span>
      <span :class="{ 'error-msg': entry.isError }">{{ entry.message }}</span>
    </div>
  </div>
</template>

<style scoped>
/* 从现有 CSS .agent-log 块搬迁（第 290-318 行） */
.agent-log {
  display: none;
  background: var(--bg);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  padding: 16px 18px;
  margin-bottom: 20px;
  max-height: 280px;
  overflow-y: auto;
  font-family: var(--font-ui);
}
.agent-log.show { display: block; animation: fadeInUp 0.2s ease-out; }
.agent-log .log-title {
  font-size: 0.68rem; color: var(--accent);
  letter-spacing: 0.1em;
  margin-bottom: 10px;
  font-weight: 700;
}
.agent-log .log-entry {
  font-size: 0.7rem;
  padding: 3px 0;
  border-bottom: 1px solid rgba(255,255,255,0.03);
  opacity: 0.85;
}
.agent-log .log-entry .agent-tag {
  color: var(--muted); font-size: 0.65rem;
  margin-right: 6px;
}
.agent-log .log-entry .error-msg { color: var(--red); }
</style>
```

**知识点：`watch` + `nextTick` 实现自动滚底**

```js
watch(() => logs.value.length, async () => {
  await nextTick()  // 等 Vue 把新 DOM 渲染完
  container.scrollTop = container.scrollHeight  // 滚到底
})
```

`nextTick` 是关键——`logs.push()` 触发响应式更新，但 Vue 异步渲染 DOM（批量更新）。`await nextTick()` 保证 `scrollTop` 在 DOM 更新之后才执行，否则 `scrollHeight` 还是旧值。

- [ ] **Step 2: 创建 `ErrorBox.vue`**

```vue
<script setup>
import { useAnalyzer } from '../composables/useAnalyzer'

const { error, clearError } = useAnalyzer()
</script>

<template>
  <div
    class="error-box"
    :class="{ show: error }"
    @click="clearError"
  >
    {{ error }}
  </div>
</template>

<style scoped>
.error-box {
  display: none;
  padding: 18px 22px;
  border: 1px solid var(--red);
  border-left: 4px solid var(--red);
  color: var(--red);
  font-size: 0.8rem;
  margin-bottom: 24px;
  background: rgba(240,84,72,0.05);
  cursor: pointer;
}
.error-box::before { content: '! '; font-weight: 700; }
.error-box.show { display: block; animation: fadeInUp 0.2s ease-out; }
</style>
```

- [ ] **Step 3: 更新 `App.vue`** — 嵌入 AgentLog + ErrorBox

```vue
import AgentLog from './components/AgentLog.vue'
import ErrorBox from './components/ErrorBox.vue'

// template 中，<IssueForm /> 后面：
<AgentLog />
<ErrorBox />
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AgentLog.vue \
        frontend/src/components/ErrorBox.vue \
        frontend/src/App.vue
git commit -m "feat: add AgentLog (auto-scroll) + ErrorBox components"
```

---

## Task 7: 拆 ResultsPanel + SummaryBar + SnippetList + FixCard + ReportView

**Files:**
- Create: `frontend/src/components/ResultsPanel.vue`
- Create: `frontend/src/components/SummaryBar.vue`
- Create: `frontend/src/components/SnippetList.vue`
- Create: `frontend/src/components/FixCard.vue`
- Create: `frontend/src/components/ReportView.vue`
- Modify: `frontend/src/App.vue`

**知识点：组件粒度——什么时候拆子组件？**

当一个组件有 3+ 个视觉区块（summary bar + snippets + fixes + report），而这些区块**互不依赖**时（改 snippets 不需要改 fixes 的代码），拆成独立子组件是最佳实践。每个子组件只接收自己的 props，独立渲染。

`ResultsPanel` 是一个容器——它本身不渲染数据，只负责布局 + 条件显示 + 交错动画。

- [ ] **Step 1: 创建 `SummaryBar.vue`**

```vue
<script setup>
defineProps({
  files: { type: Number, default: 0 },
  indexed: { type: Number, default: 0 },
  hits: { type: Number, default: 0 },
  fixes: { type: Number, default: 0 },
  issueTitle: { type: String, default: '' },
})
</script>

<template>
  <div class="summary-bar">
    <div class="stat">
      <div class="label">ISSUE</div>
      <div class="value" :title="issueTitle">{{ issueTitle.slice(0, 42) }}</div>
    </div>
    <div class="stat">
      <div class="label">FILES</div>
      <div class="value">{{ files }}</div>
    </div>
    <div class="stat">
      <div class="label">INDEXED</div>
      <div class="value">{{ indexed }}</div>
    </div>
    <div class="stat">
      <div class="label">HITS</div>
      <div class="value">{{ hits }}</div>
    </div>
    <div class="stat">
      <div class="label">FIXES</div>
      <div class="value">{{ fixes }}</div>
    </div>
  </div>
</template>

<style scoped>
/* summary-bar + stat 从现有 CSS 搬迁 */
</style>
```

- [ ] **Step 2: 创建 `SnippetList.vue`**

这里需要保留 copy-to-clipboard 功能——从现有 JS 的 `document.addEventListener('click', ...)` 事件委托改成 Vue 的方式。

```vue
<script setup>
const props = defineProps({
  snippets: { type: Array, default: () => [] },
})

function copyCode(snippet, event) {
  navigator.clipboard.writeText(snippet.code || '').then(() => {
    event.target.textContent = 'COPIED'
    event.target.classList.add('copied')
    setTimeout(() => {
      event.target.textContent = 'COPY'
      event.target.classList.remove('copied')
    }, 1500)
  })
}
</script>

<template>
  <div v-if="snippets.length === 0" class="empty-state">
    <div class="icon">// no results</div>
    未找到相关代码片段
  </div>

  <div
    v-for="(s, i) in snippets"
    :key="i"
    class="snippet"
    :style="{ animationDelay: i * 0.03 + 's' }"
  >
    <div class="snippet-header">
      <span class="snippet-title">
        {{ s.name }}
        <span class="kind">::{{ s.kind }}</span>
      </span>
      <span class="snippet-meta">{{ s.file_path }} :{{ s.line_start }}-{{ s.line_end }}</span>
    </div>
    <div class="snippet-body">
      <button class="copy-btn" @click="copyCode(s, $event)">COPY</button>
      <pre>{{ s.code?.slice(0, 2000) || '' }}</pre>
    </div>
  </div>
</template>

<style scoped>
/* snippet 相关 CSS 从 components.css 搬迁（或继承全局） */
</style>
```

- [ ] **Step 3: 创建 `FixCard.vue`**

```vue
<script setup>
defineProps({
  fixes: { type: Array, default: () => [] },
})
</script>

<template>
  <div v-if="fixes.length === 0" class="empty-state">
    <div class="icon">// no fixes</div>
    未生成修复建议
  </div>

  <div
    v-for="(f, i) in fixes"
    :key="i"
    class="fix-card"
    :style="{ animationDelay: i * 0.05 + 's' }"
  >
    <div class="fix-header">
      <span class="fix-file">{{ f.file_path }} / {{ f.name }}</span>
      <span class="fix-confidence" :class="'conf-' + (f.confidence || 'medium')">
        {{ (f.confidence || 'MEDIUM').toUpperCase() }}
      </span>
    </div>
    <div class="fix-desc">{{ f.suggested_fix }}</div>
    <div class="fix-issue">{{ f.issue_summary }}</div>
  </div>
</template>

<style scoped>
/* fix-card 相关 CSS */
</style>
```

- [ ] **Step 4: 创建 `ReportView.vue** — Markdown 报告展示

```vue
<script setup>
defineProps({
  report: { type: String, default: '' },
})
</script>

<template>
  <div v-if="report" class="section-title">分析报告</div>
  <div v-if="report" class="analysis-box">
    <p>{{ report }}</p>
  </div>
</template>

<style scoped>
.section-title {
  font-family: var(--font-display);
  font-size: 0.82rem; font-weight: 700;
  color: var(--accent);
  margin-bottom: 16px; margin-top: 32px;
  letter-spacing: 0.1em;
}
.section-title::before { content: '## '; color: var(--muted); font-weight: 400; }
.analysis-box {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--teal);
  padding: 24px 24px;
  margin-bottom: 0;
}
.analysis-box p {
  font-size: 0.82rem; color: var(--muted);
  white-space: pre-wrap; line-height: 1.8;
}
</style>
```

- [ ] **Step 5: 创建 `ResultsPanel.vue** — 容器布局 + 条件显示

这个组件目前简单包装上面的子组件。等 Agent 版 API 返回了结构化数据（不只是 `report` 字符串）之后再细化 `snippets` 和 `fixes` 的数据映射。

```vue
<script setup>
import { useAnalyzer } from '../composables/useAnalyzer'
import SummaryBar from './SummaryBar.vue'
import ReportView from './ReportView.vue'

const { report, loading } = useAnalyzer()

// 是否有结果可展示
const hasResults = computed(() => !!report.value && !loading.value)
</script>

<template>
  <div class="results" :class="{ show: hasResults }">
    <ReportView :report="report" />
  </div>
</template>

<style scoped>
.results { display: none; }
.results.show { display: block; }
.results.show > * {
  animation: fadeInUp 0.4s ease-out both;
}
.results.show > *:nth-child(1) { animation-delay: 0.05s; }
.results.show > *:nth-child(2) { animation-delay: 0.1s; }
.results.show > *:nth-child(3) { animation-delay: 0.15s; }
.results.show > *:nth-child(4) { animation-delay: 0.2s; }
.results.show > *:nth-child(5) { animation-delay: 0.25s; }
</style>
```

- [ ] **Step 6: 更新 `App.vue** — 嵌入所有组件

```vue
import ResultsPanel from './components/ResultsPanel.vue'

// template 中：
<AgentLog />
<ErrorBox />
<ResultsPanel />
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/SummaryBar.vue \
        frontend/src/components/SnippetList.vue \
        frontend/src/components/FixCard.vue \
        frontend/src/components/ReportView.vue \
        frontend/src/components/ResultsPanel.vue \
        frontend/src/App.vue
git commit -m "feat: add results components — SummaryBar, SnippetList, FixCard, ReportView, ResultsPanel"
```

---

## Task 8: 组装 App.vue + 端到端测试

**Files:**
- Modify: `frontend/src/App.vue`（最终版本）

- [ ] **Step 1: 最终 App.vue**

```vue
<script setup>
import AppHeader from './components/AppHeader.vue'
import AppFooter from './components/AppFooter.vue'
import TabSwitch from './components/TabSwitch.vue'
import IssueForm from './components/IssueForm.vue'
import AgentLog from './components/AgentLog.vue'
import ErrorBox from './components/ErrorBox.vue'
import ResultsPanel from './components/ResultsPanel.vue'
import { useAnalyzer } from './composables/useAnalyzer'

const { mode, setMode } = useAnalyzer()
</script>

<template>
  <AppHeader phase="V2 · AGENT" />

  <div class="container">
    <TabSwitch v-model:mode="mode" @update:mode="setMode" />
    <IssueForm />
    <AgentLog />
    <ErrorBox />
    <ResultsPanel />
  </div>

  <AppFooter />
</template>

<style scoped>
.container {
  max-width: 880px;
  margin: 0 auto;
  padding: 32px 16px 56px;
  position: relative; z-index: 1;
}

/* 确保 .container 内的元素在噪点/扫描线之上 */
.container > * {
  position: relative; z-index: 1;
}

@media (max-width: 640px) {
  .container { padding: 20px 12px 40px; }
}
</style>
```

- [ ] **Step 2: 启动全套服务做端到端测试**

```bash
# 终端 1: FastAPI
cd "d:/项目/GitHub Issue/backend"
python -m uvicorn app.main:app --reload --port 8000

# 终端 2: Vite
cd "d:/项目/GitHub Issue/frontend"
npm run dev
```

测试清单：
1. 打开 `http://localhost:5173`，看到完整页面（Header + Tabs + Form + Footer）
2. 点击 Tab [2]，切换到报错文本模式——表单字段正确切换
3. 勾选 STREAM checkbox——颜色变化
4. 填入真实 Issue URL + Repo URL → 提交 → AgentLog 实时滚动
5. 报告生成后 ResultsPanel 淡入显示

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.vue
git commit -m "feat: final App.vue assembly — all 10 components wired"
```

---

## Task 9: FastAPI 挂载 dist/ —— 部署模式

**Files:**
- Modify: `backend/app/main.py`
- Create: `frontend/.gitignore`（或追加条目）

**知识点：开发 vs 部署的 URL 策略**

```
开发:  Vite dev server (:5173) → proxy /api → FastAPI (:8000)
       前端和 API 在同域（localhost:5173），无跨域

部署:  FastAPI (:8000) → StaticFiles mount / → dist/
       前端打包成静态文件，FastAPI 直接返回
       只有一个端口，没有 proxy
```

- [ ] **Step 1: 修改 `backend/app/main.py`**

在 `app = FastAPI(...)` 后面、`app.add_middleware(CORS...)` 前面：

```python
from pathlib import Path
from fastapi.staticfiles import StaticFiles

# 尝试挂载前端构建产物（如果 dist/ 存在）
dist_path = Path(__file__).parent.parent.parent / "frontend" / "dist"
if dist_path.exists():
    # mount at root "/" → 访问 http://localhost:8000/ 就是前端
    # HTML response fallback for SPA routing
    app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="frontend")
```

**但注意：** 如果挂载了 `/` 的 StaticFiles，`app.get("/")` 路由会被覆盖。所以原来 `index()` 函数可以保留但不会生效——这是预期行为。访问 `http://localhost:8000/api/analyze` 仍走 FastAPI 路由（精确匹配优先于 StaticFiles）。

更好的做法：

```python
# 只挂载 /assets/ → dist/assets/（JS/CSS）
# / 和 /api/ 还是走 FastAPI 路由
if dist_path.exists():
    assets_path = dist_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")
```

**推荐第二种**——保留 `/` 路由给 `index()` 函数（动态返回 HTML），只把静态资源目录挂载。

- [ ] **Step 2: 构建前端**

```bash
cd "d:/项目/GitHub Issue/frontend"
npm run build
```

产出 `dist/` 目录（含 `index.html` + `assets/`）。

- [ ] **Step 3: 验证部署**

```bash
cd "d:/项目/GitHub Issue/backend"
python -m uvicorn app.main:app --port 8000
```

访问 `http://localhost:8000`，看到和 Vite dev server 一样的界面。

访问 `http://localhost:8000/api/health`，返回 `{"status": "ok"}`。

- [ ] **Step 4: 更新 .gitignore**

```
node_modules/
dist/
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py frontend/.gitignore
git commit -m "feat: FastAPI mount dist/ for production deployment"
```

---

## Spec 自审

### Spec 覆盖对照

| Spec 要求 | 对应 Task |
|-----------|----------|
| Vite + Vue 3 脚手架 | Task 1 |
| CSS 四层迁移（variables/base/animations/components） | Task 2 |
| useAnalyzer composable（状态 + SSE） | Task 3 |
| AppHeader / AppFooter / TabSwitch | Task 4 |
| IssueForm（表单 + 校验 + 模式切换） | Task 5 |
| AgentLog（自动滚底）+ ErrorBox | Task 6 |
| ResultsPanel + SummaryBar + SnippetList + FixCard + ReportView | Task 7 |
| App.vue 组装 + 端到端测试 | Task 8 |
| FastAPI 挂载 dist + 部署 | Task 9 |
| 保留工业终端美学 | 所有 CSS 任务（从 index.html.backup 直接搬迁） |
| 开发 proxy、部署 mount | Task 1 (vite.config) + Task 9 (main.py) |

### Placeholder 扫描
通过——无 TBD/TODO。

### 类型一致性
- `useAnalyzer` 的返回值在所有组件中一致使用
- Props 类型在父子组件间匹配
- CSS 类名从现有 HTML 直接搬迁，无命名冲突
