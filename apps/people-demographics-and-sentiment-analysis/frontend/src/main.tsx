import { DepthAIContext } from '@luxonis/depthai-viewer-common';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router';
import './index.css';
import '@luxonis/depthai-viewer-common/styles';
import '@luxonis/ui-components/styles.css';
import '@luxonis/depthai-pipeline-lib/styles';
import App from './App.tsx';
import { PEOPLE_ANALYTICS_ACTIVE_SERVICES } from './services.ts';

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
			<DepthAIContext activeServices={PEOPLE_ANALYTICS_ACTIVE_SERVICES}>
				<Routes>
					<Route path="/" element={<App />} />
				</Routes>
			</DepthAIContext>
		</BrowserRouter>
	</StrictMode>,
);
