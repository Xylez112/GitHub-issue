import { createApp } from 'vue'
import App from './App.vue'

// 全局样式（非 scoped，所有组件自动继承）
import './styles/variables.css'
import './styles/base.css'
import './styles/animations.css'
import './styles/components.css'

const app = createApp(App)
app.mount('#app')
