import "@luxonis/common-fe-components/styles";
import "@luxonis/depthai-pipeline-lib/styles";
import { DepthAIContext } from "@luxonis/depthai-viewer-common";
import "@luxonis/depthai-viewer-common/styles";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import App from "./App.tsx";
import "./index.css";

function getBasePath(): string {
    return window.location.pathname.match(/^\/\d+\.\d+\.\d+\/$/)?.[0] ?? "";
}

const queryClient = new QueryClient();

createRoot(document.getElementById("root")!).render(
    <StrictMode>
        <BrowserRouter basename={getBasePath()}>
            <DepthAIContext messageHandlerVersion="v1">
                <QueryClientProvider client={queryClient}>
                    <App />
                </QueryClientProvider>
            </DepthAIContext>
        </BrowserRouter>
    </StrictMode>,
);
