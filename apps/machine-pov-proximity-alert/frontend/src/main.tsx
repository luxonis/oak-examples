import { DepthAIContext } from '@luxonis/depthai-viewer-common';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import '@luxonis/depthai-viewer-common/styles';
import '@luxonis/ui-components/styles.css';
import '@luxonis/depthai-pipeline-lib/styles';
import App from './App.tsx';

const rootElement = document.getElementById('root');

if (!rootElement) {
	throw new Error('Root element was not found.');
}

const queryClient = new QueryClient();

createRoot(rootElement).render(
	<StrictMode>
		<DepthAIContext messageHandlerVersion="v1">
			<QueryClientProvider client={queryClient}>
				<App />
			</QueryClientProvider>
		</DepthAIContext>
	</StrictMode>,
);
