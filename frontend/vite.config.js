import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiUrl = env.VITE_API_URL?.trim()

  if (mode === 'production') {
    if (!apiUrl) {
      throw new Error('VITE_API_URL is required for a production build.')
    }
    const parsed = new URL(apiUrl)
    if (parsed.protocol !== 'https:') {
      throw new Error('VITE_API_URL must use HTTPS in production.')
    }
    if (!parsed.pathname.replace(/\/+$/, '').endsWith('/api')) {
      throw new Error('VITE_API_URL must end with /api.')
    }
  }

  return {
    plugins: [react()],
  }
})
