import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import './index.css';
import '@luxonis/depthai-viewer-common/styles';
import '@luxonis/common-fe-components/styles';
import '@luxonis/depthai-pipeline-lib/styles';
import App from './App.tsx';
import {BrowserRouter, Route, Routes} from "react-router";
import {DepthAIContext} from "@luxonis/depthai-viewer-common";

createRoot(document.getElementById('root')!).render(
    <StrictMode>
            <BrowserRouter>
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
