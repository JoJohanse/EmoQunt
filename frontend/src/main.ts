import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
// Element Plus 暗色主题变量（配合 html.dark class，见 stores/ui.ts）
import 'element-plus/theme-chalk/dark/css-vars.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import { createPersistedState } from './stores/persist'
import './assets/main.css'

const app = createApp(App)

// 注册 Element Plus 图标为全局组件
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

const pinia = createPinia()
// 本地持久化插件（localStorage，store 通过 persist 选项 opt-in）
pinia.use(createPersistedState())

app.use(pinia)
app.use(router)
app.use(ElementPlus)

app.mount('#app')
