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
			output: {
				format: "esm",
			},
		},
	},
});