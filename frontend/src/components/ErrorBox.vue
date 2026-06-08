<script setup>
import { useAnalyzer } from '../composables/useAnalyzer'

const { error, clearError } = useAnalyzer()
</script>

<template>
  <div
    class="error-box"
    :class="{ show: error }"
    @click="clearError"
  >
    {{ error }}
  </div>
</template>

<style scoped>
.error-box {
  display: none;
  padding: 18px 22px;
  border: 1px solid var(--red);
  border-left: 4px solid var(--red);
  color: var(--red);
  font-size: 0.8rem;
  margin-bottom: 24px;
  background: rgba(240,84,72,0.05);
  cursor: pointer;
}
.error-box::before { content: '! '; font-weight: 700; }
.error-box.show { display: block; animation: fadeInUp 0.2s ease-out; }
</style>
