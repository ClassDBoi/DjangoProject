import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'rewrite-internal',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          // If the URL starts with /internal, rewrite it to /private.html internally
          if (req.url.startsWith('/internal')) {
            req.url = '/index.html';
          }
          next();
        });
      },
    },
  ],
  build: {
  rollupOptions: {
    input: {
      main: resolve(__dirname, 'index.html'),
      },
    },
  },
  server: {
    host: true,
    port: 5173,
    // Lets the frontend call /api/... without VITE_API_BASE or CORS setup in development.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});