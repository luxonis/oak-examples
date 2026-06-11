import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { fileURLToPath, URL } from "node:url";

const cookieShim = fileURLToPath(new URL("./src/vendor/cookie-shim.ts", import.meta.url));
const setCookieParserShim = fileURLToPath(
  new URL("./src/vendor/set-cookie-parser-shim.ts", import.meta.url),
);

export default defineConfig({
  base: "",
  resolve: {
    alias: {
      cookie: cookieShim,
      "cookie/dist/index.js": cookieShim,
      "set-cookie-parser": setCookieParserShim,
      "set-cookie-parser/lib/set-cookie.js": setCookieParserShim,
    },
  },
  plugins: [react()],
  build: {
    sourcemap: false,
    rollupOptions: {
      output: {
        format: "esm",
      },
    },
  },
  server: {
    sourcemapIgnoreList: () => true,
  },
  optimizeDeps: {
    exclude: [
      "@luxonis/depthai-viewer-common",
      "@luxonis/depthai-pipeline-lib",
      "@luxonis/visualizer-protobuf",
      "@luxonis/remote-connection",
    ],
    include: [
      "@luxonis/common-fe-components",
    ],
  },
  define: {
    global: {},
  },
  worker: {
    format: "es",
  },
});
