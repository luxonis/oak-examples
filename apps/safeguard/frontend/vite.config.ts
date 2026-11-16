import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
	base: '',
	plugins: [react()],
	resolve: {
		dedupe: ['react', 'react-dom'],
	},
	// Needed by Foxglove.
	define: {
		global: {},
	},
	worker: {
		format: 'es',
	},
	build: {
		rollupOptions: {
			output: {
				format: 'esm',
			},
		},
	},
});
