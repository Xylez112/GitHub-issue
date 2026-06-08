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
.snippet {
  background: var(--surface);
  border: 1px solid var(--border);
  margin-bottom: 10px;
  transition: all 0.15s;
  position: relative;
}
.snippet:hover { border-color: #3a3a30; }
.snippet-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap; gap: 8px;
}
.snippet-title {
  font-weight: 500; font-size: 0.8rem;
  color: var(--teal);
  font-family: var(--font-ui);
}
.snippet-title .kind {
  color: var(--muted); font-weight: 400;
  font-style: italic; font-size: 0.75rem;
}
.snippet-meta {
  font-size: 0.66rem; color: var(--muted);
  background: var(--bg); padding: 4px 10px;
  letter-spacing: 0.04em;
}
.snippet-body { position: relative; }
.snippet-body pre {
  margin: 0; padding: 18px 20px;
  background: var(--bg);
  font-family: var(--font-ui);
  font-size: 0.78rem; line-height: 1.6;
  color: var(--text);
  overflow-x: auto;
  white-space: pre;
}
.copy-btn {
  position: absolute; top: 10px; right: 10px;
  background: var(--surface); color: var(--muted);
  border: 1px solid var(--border);
  padding: 5px 14px;
  font-family: var(--font-ui); font-size: 0.66rem;
  cursor: pointer;
  opacity: 0;
  transition: all 0.15s;
  letter-spacing: 0.06em;
}
.snippet-body:hover .copy-btn { opacity: 1; }
.copy-btn:hover { color: var(--accent); border-color: var(--accent); }
.copy-btn.copied { color: var(--teal); border-color: var(--teal); }
.empty-state {
  text-align: center; padding: 56px 20px;
  color: var(--muted); font-size: 0.8rem;
  border: 1px dashed var(--border);
}
.empty-state .icon {
  font-size: 2.2rem; margin-bottom: 12px;
  opacity: 0.3; font-family: var(--font-display);
}
@media (max-width: 640px) {
  .snippet-header { flex-direction: column; align-items: flex-start; }
}
</style>
