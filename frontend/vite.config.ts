import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'


// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  
  // 👇 加上这一段，解决外网访问报错
  server: {
    allowedHosts: true,
    host: "0.0.0.0",
    port: 5173
  }
})
