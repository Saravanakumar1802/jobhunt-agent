import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Dev proxy: the browser calls /api on the same origin, Vite forwards to FastAPI.
    // Set API_PORT if 8000 is taken by another app, e.g.  API_PORT=8001 npm run dev
    proxy: { "/api": { target: `http://127.0.0.1:${process.env.API_PORT || 8000}`, changeOrigin: true } },
  },
  // `vite preview` is what Render runs; it rejects unknown hosts unless listed here.
  preview: {
    host: "0.0.0.0",
    allowedHosts: ["jobhunt-agent-1.onrender.com"],
  },
  build: {
    // three.js (~900 kB) is lazy-loaded only for the 3D scenes, so its size doesn't block first paint.
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        // Keep the heavy 3D stack in its own chunk so app pages load fast.
        manualChunks(id) {
          if (/three|@react-three/.test(id)) return "three";
          if (/gsap/.test(id)) return "gsap";
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.js"],
    css: false,
  },
});
