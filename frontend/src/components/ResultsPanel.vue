<script setup>
import { computed } from 'vue'
import { useAnalyzer } from '../composables/useAnalyzer'
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
