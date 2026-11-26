import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { vReveal } from './directives/reveal'
import './styles/tokens.css'
import './styles/styles.css'
import { useSession } from './composables/session'

if (!/^\/admin(?:\/|$)/.test(location.pathname)) void useSession().restore()

createApp(App).use(router).directive('reveal', vReveal).mount('#app')
