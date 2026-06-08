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
.fix-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 4px solid var(--accent);
  padding: 18px 22px;
  margin-bottom: 10px;
  box-shadow: 4px 4px 0 rgba(0,0,0,0.3);
  transition: all 0.15s;
}
.fix-card:hover { border-left-color: var(--teal); }
.fix-header {
  display: flex; justify-content: space-between;
  align-items: center; margin-bottom: 12px;
  flex-wrap: wrap; gap: 8px;
}
.fix-file {
  font-weight: 500; font-size: 0.8rem;
  color: var(--text);
  font-family: var(--font-ui);
}
.fix-confidence {
  font-size: 0.62rem; padding: 3px 14px;
  font-weight: 700; letter-spacing: 0.1em;
}
.conf-high   { background: rgba(64,196,160,0.1); color: var(--teal); border: 1px solid var(--teal); }
.conf-medium { background: rgba(240,192,64,0.1); color: var(--accent); border: 1px solid var(--accent); }
.conf-low    { background: rgba(240,84,72,0.1); color: var(--red); border: 1px solid var(--red); }
.fix-desc {
  font-size: 0.82rem; color: var(--text);
  margin-bottom: 8px; line-height: 1.7;
}
.fix-issue {
  font-size: 0.72rem; color: var(--muted);
  font-style: italic;
}
.fix-issue::before { content: '↳ '; color: var(--accent-dim); }
.empty-state {
  text-align: center; padding: 56px 20px;
  color: var(--muted); font-size: 0.8rem;
  border: 1px dashed var(--border);
}
.empty-state .icon {
  font-size: 2.2rem; margin-bottom: 12px;
  opacity: 0.3; font-family: var(--font-display);
}
</style>
