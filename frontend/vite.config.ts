/**
 * Vite configuration - this file is the contract with the FastAPI backend.
 *
 * Two things matter to the backend:
 *
 * 1. `build.outDir` MUST stay `dist`. `app/main.py` mounts that directory at `/`
 *    (`StaticFiles(directory=str(settings.STATIC_DIR))`), so a rename breaks the
 *    deployed site silently.
 * 2. `base: './'` makes every emitted asset reference relative. The site then
 *    works whether it is served from `/` or from a sub-path, and the build makes
 *    zero absolute-asset assumptions.
 *
 * The dev proxy exists so the browser only ever makes same-origin requests. CORS
 * is therefore never exercised in development - if it works with the proxy on, it
 * will work in production where the API and the SPA share an origin.
 *
 * No CDN, no remote fonts, no remote images: everything ships in the bundle or is
 * inlined. See the project constraint that the UI renders with zero network egress
 * beyond its own backend.
 */
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/** Where the FastAPI development server is expected to be listening. */
const BACKEND_ORIGIN = 'http://127.0.0.1:8000'

export default defineConfig(({ command }) => ({
  base: './',
  plugins: [react()],

  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
  },

  server: {
    port: 5173,
    strictPort: true,
    proxy:
      command === 'serve'
        ? {
            '/api': { target: BACKEND_ORIGIN, changeOrigin: false },
            '/docs': { target: BACKEND_ORIGIN, changeOrigin: false },
            // No /redoc entry: the backend disables that page because it loads a
            // Montserrat/Roboto stylesheet from fonts.googleapis.com, which
            // breaks the no-external-font rule. Proxying it would only forward
            // the 404.
            '/openapi.json': { target: BACKEND_ORIGIN, changeOrigin: false },
          }
        : undefined,
  },

  preview: {
    port: 4173,
    strictPort: true,
  },
}))
