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
