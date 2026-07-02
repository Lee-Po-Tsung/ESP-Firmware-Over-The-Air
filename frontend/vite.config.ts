import { defineConfig, loadEnv } from 'vite'
import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import babel from '@rolldown/plugin-babel'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [
      react(),
      babel({ presets: [reactCompilerPreset()] })
    ],
    server: {
      proxy: {
        '/backend': {
          target: env.VITE_BACKEND,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/backend/, '') // 移除路徑中的 /backend
        }
      }
    }
  };
})
