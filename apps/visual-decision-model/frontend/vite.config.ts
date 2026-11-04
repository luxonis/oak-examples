import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const depthaiPipelinePackageJson = '\0depthai-pipeline-lib-package-json';

// https://vite.dev/config/
export default defineConfig({
	base: '',
	plugins: [
		react(),
		{
			name: 'depthai-pipeline-lib-package-json',
			resolveId(source, importer) {
				const pipelineLibEntry =
					'/node_modules/@luxonis/depthai-pipeline-lib/dist/src/index.js';
				const normalizedImporter = importer?.replace(/\\/g, '/');

				if (
					source === '../package.json' &&
					normalizedImporter?.slice(-pipelineLibEntry.length) ===
						pipelineLibEntry
				) {
					return depthaiPipelinePackageJson;
				}
			},
			load(id) {
				if (id === depthaiPipelinePackageJson) {
					return 'export const version = "4.0.0"; export default { version };';
				}
			},
		},
	],
	// This is needed by FoxGlove
	define: {
		global: {},
	},
	worker: {
		format: 'es',
	},
	build: {
		rollupOptions: {
			// OAK's build container has a low file-descriptor limit.
			maxParallelFileOps: 8,
			output: {
				format: 'esm',
			},
		},
	},
});
