import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import './index.css';
import '@luxonis/depthai-viewer-common/styles';
import '@luxonis/common-fe-components/styles';
import '@luxonis/depthai-pipeline-lib/styles';
import App from './App.tsx';
import {BrowserRouter, Route, Routes} from "react-router";
import {DepthAIContext} from "@luxonis/depthai-viewer-common";

// This function extracts the base path with app version from the current URL.
// This is essential for access via domain luxonis.app
function getBasePath(): string {
  return window.location.pathname.match(/^\/\d+\.\d+\.\d+\/$/)?.[0] ?? ''
}

createRoot(document.getElementById('root')!).render(
    <StrictMode>
            <BrowserRouter basename={getBasePath()}>
                <DepthAIContext activeServices={
                    // @ts-ignore - We're using an example service here which isn't part of the DAI services enum
                    ['Custom Service']
                }>
                <Routes>
                    <Route path="/" element={<App/>}/>
                </Routes>
                </DepthAIContext>
            </BrowserRouter>
    </StrictMode>,
);
