import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import ToastHost from './components/ToastHost.vue'
import './assets/styles/variables.css'
import './assets/styles/global.css'

const app = createApp(App)
app.use(createPinia())
app.component('ToastHost', ToastHost)
app.mount('#app')
