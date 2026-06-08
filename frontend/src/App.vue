<script setup>
import { useAnalyzer } from './composables/useAnalyzer'
import AppHeader from './components/AppHeader.vue'
import AppFooter from './components/AppFooter.vue'
import TabSwitch from './components/TabSwitch.vue'

const { mode } = useAnalyzer()
</script>

<template>
  <AppHeader phase="V2 · AGENT" />
  <div class="container">
    <TabSwitch v-model:mode="mode" />
    <!-- 后续 Task 在这里加入 IssueForm、AgentLog、ErrorBox、ResultsPanel -->
    <div style="padding:40px;text-align:center;color:var(--teal);font-family:var(--font-display)">
      > components ready
    </div>
  </div>
  <AppFooter />
</template>

<style scoped>
.container {
  max-width: 880px;
  margin: 0 auto;
  padding: 32px 16px 56px;
  position: relative; z-index: 1;
}
</style>
