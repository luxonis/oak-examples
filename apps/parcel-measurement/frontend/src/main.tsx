import { DepthAIContext } from '@luxonis/depthai-viewer-common';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router';
import './index.css';
import '@luxonis/depthai-viewer-common/styles';
import '@luxonis/ui-components/styles.css';
import '@luxonis/depthai-pipeline-lib/styles';
import App from './App';

const basePath =
	window.location.pathname.match(/^\/\d+\.\d+\.\d+\/$/)?.[0] ?? '';
const queryClient = new QueryClient();
const root = document.getElementById('root');
if (!root) throw new Error('Root element was not found.');

createRoot(root).render(
	<StrictMode>
		<BrowserRouter basename={basePath}>
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
