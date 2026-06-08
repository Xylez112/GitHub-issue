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
