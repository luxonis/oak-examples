import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// https://vite.dev/config/
export default defineConfig({
	base: "",
	plugins: [react(),],
	// This is needed by FoxGlove
	define: {
		global: {},
	},
	worker: {
		format: "es",
	},
	build: {
		rollupOptions: {
			// OAK's build container has a low file-descriptor limit.
			maxParallelFileOps: 8,
			output: {
				format: "esm",
			},
		},
	},
});
