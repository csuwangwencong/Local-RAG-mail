import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import './styles/base.css'
import './styles/mail-layout.css'

createApp(App).use(createPinia()).use(ElementPlus).mount('#app')
