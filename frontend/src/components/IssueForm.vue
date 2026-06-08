<script setup>
import { ref, computed } from 'vue'
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
  if (!repoUrl.value.trim()) return

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
