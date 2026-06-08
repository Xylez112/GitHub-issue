<script setup>
import { useAnalyzer } from './composables/useAnalyzer'
import AppHeader from './components/AppHeader.vue'
import AppFooter from './components/AppFooter.vue'
import TabSwitch from './components/TabSwitch.vue'
import IssueForm from './components/IssueForm.vue'
import AgentLog from './components/AgentLog.vue'
import ErrorBox from './components/ErrorBox.vue'
import ResultsPanel from './components/ResultsPanel.vue'

const { mode } = useAnalyzer()
</script>

<template>
  <AppHeader phase="V2 · AGENT" />
  <div class="container">
    <TabSwitch v-model:mode="mode" />
    <IssueForm />
    <AgentLog />
    <ErrorBox />
    <ResultsPanel />
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
