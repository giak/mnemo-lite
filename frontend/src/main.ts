import { createApp } from 'vue'
import router from './router'
import App from './App.vue'
import './style.css'

// v-network-graph for graph visualization
import VNetworkGraph from 'v-network-graph'
import 'v-network-graph/lib/style.css'

const app = createApp(App)

app.use(router)
app.use(VNetworkGraph)

app.mount('#app')
