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
