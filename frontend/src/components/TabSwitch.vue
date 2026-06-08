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
