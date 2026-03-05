import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "",
  define: { global: {} },
  plugins: [react()],
  build: {
    rollupOptions: {
      output: { format: "esm" }
    }
  },
  resolve: {
    alias: {
      tslib: "tslib/tslib.es6.js",
    },
  }
});