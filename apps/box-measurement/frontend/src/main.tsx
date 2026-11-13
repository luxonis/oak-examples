import { DepthAIContext } from '@luxonis/depthai-viewer-common';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router';
import './index.css';
import '@luxonis/depthai-viewer-common/styles';
import '@luxonis/ui-components/styles.css';
import '@luxonis/depthai-pipeline-lib/styles';
// Panda styles for the views still built on common-fe-components.
import './panda.css';
import '@luxonis/common-fe-components/styles';
import App from './App.tsx';

// extracts the base path with app version, essential for access via domain luxonis.app
function getBasePath(): string {
	return window.location.pathname.match(/^\/\d+\.\d+\.\d+\/$/)?.[0] ?? '';
}

const queryClient = new QueryClient();

const rootElement = document.getElementById('root');

if (!rootElement) {
	throw new Error('Root element was not found.');
}

createRoot(rootElement).render(
	<StrictMode>
		<BrowserRouter basename={getBasePath()}>
			<DepthAIContext>
				<QueryClientProvider client={queryClient}>
					<Routes>
						<Route path="/" element={<App />} />
					</Routes>
				</QueryClientProvider>
			</DepthAIContext>
		</BrowserRouter>
	</StrictMode>,
);
