import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Fail loudly instead of falling back to 5174+ — server.py checks the Origin,
  // and a shifted port would turn every Deploy into a 403.
  server: { host: 'localhost', port: 5173, strictPort: true },
})
