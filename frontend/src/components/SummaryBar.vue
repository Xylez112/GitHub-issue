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
.summary-bar {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  margin-bottom: 28px;
}
.stat {
  background: var(--surface);
  padding: 20px 18px;
  text-align: center;
  transition: background 0.15s;
}
.stat:hover { background: #181816; }
.stat .label {
  font-size: 0.65rem; color: var(--muted);
  letter-spacing: 0.15em;
  margin-bottom: 6px;
}
.stat .value {
  font-family: var(--font-display);
  font-size: 1.2rem; font-weight: 700;
  color: var(--text);
}
@media (max-width: 640px) {
  .summary-bar { grid-template-columns: repeat(2, 1fr); }
}
</style>
