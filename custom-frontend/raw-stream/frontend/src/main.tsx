import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import '@luxonis/depthai-viewer-common/styles';
import '@luxonis/ui-components/styles.css';
import '@luxonis/depthai-pipeline-lib/styles';
import { DepthAIContext } from '@luxonis/depthai-viewer-common';
import { BrowserRouter, Route, Routes } from 'react-router';
import App from './App.tsx';

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
			<DepthAIContext
				activeServices={
					// @ts-ignore - We're using an example service here which isn't part of the DAI services enum
					['Message Service']
				}
				withDebugLogs
			>
				<Routes>
					<Route path="/" element={<App />} />
				</Routes>
			</DepthAIContext>
		</BrowserRouter>
	</StrictMode>,
);
