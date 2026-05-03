import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173,
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
