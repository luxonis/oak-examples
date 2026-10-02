import react from '@vitejs/plugin-react';
import { type Plugin, defineConfig } from 'vite';

const depthaiPipelinePackageJson = '\0depthai-pipeline-lib-package-json';

function depthaiPipelinePackageJsonPlugin(): Plugin {
	const depthaiPipelineEntry =
		'/node_modules/@luxonis/depthai-pipeline-lib/dist/src/index.js';

	return {
		name: 'depthai-pipeline-lib-package-json',
		resolveId(source, importer) {
			const normalizedImporter = importer?.replace(/\\/g, '/');

			if (
				source === '../package.json' &&
				normalizedImporter?.slice(-depthaiPipelineEntry.length) ===
					depthaiPipelineEntry
			) {
				return depthaiPipelinePackageJson;
			}
			return null;
		},
		load(id) {
			if (id === depthaiPipelinePackageJson) {
				return 'export const version = "4.0.0"; export default { version };';
			}
			return null;
		},
	};
}

export default defineConfig({
	base: '',
	plugins: [react(), depthaiPipelinePackageJsonPlugin()],
	define: {
		global: {},
	},
	worker: {
		format: 'es',
	},
	build: {
		rollupOptions: {
			maxParallelFileOps: 8,
			output: {
				format: 'esm',
			},
		},
	},
});
