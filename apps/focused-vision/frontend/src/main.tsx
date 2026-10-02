import { DepthAIContext } from '@luxonis/depthai-viewer-common';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router';
import './styles.css';
import '@luxonis/depthai-viewer-common/styles';
import '@luxonis/ui-components/styles.css';
import '@luxonis/depthai-pipeline-lib/styles';
import App from './App.tsx';

// This function extracts the base path with app version from the current URL.
// This is essential for access via domain luxonis.app
function getBasePath(): string {
	return window.location.pathname.match(/^\/\d+\.\d+\.\d+\/$/)?.[0] ?? '';
}

const rootElement = document.getElementById('root');

if (!rootElement) {
	throw new Error('Root element was not found.');
}

createRoot(rootElement).render(
	<StrictMode>
		<BrowserRouter basename={getBasePath()}>
			<DepthAIContext activeServices={[]}>
				<Routes>
					<Route path="/" element={<App />} />
				</Routes>
			</DepthAIContext>
		</BrowserRouter>
	</StrictMode>,
);
