import { defineConfig } from "vite";

export default defineConfig({
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/live": {
        target: "http://127.0.0.1:8085",
        changeOrigin: true,
      },
      "/demo": {
        target: "http://127.0.0.1:8085",
        changeOrigin: true,
      },
    },
  },
});
