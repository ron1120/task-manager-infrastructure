import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // `npm run dev`: forward /assistant/ to the pagewise container published on port 8010.
    proxy: {
      '/assistant': {
        target: 'http://localhost:8010',
        rewrite: (path) => path.replace(/^\/assistant/, ''),
      },
    },
  },
});
