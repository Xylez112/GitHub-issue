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
