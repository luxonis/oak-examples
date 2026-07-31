// MessageInput.tsx
import React, { useCallback, useEffect, useRef, useState } from "react";
import { css } from "../styled-system/css/css.mjs";
import { useNotifications } from "./Notifications";
import { useConnection } from "@luxonis/depthai-viewer-common";
import { Button } from "@luxonis/common-fe-components";

// Backend services registered in the pipeline
const UPDATE_SERVICE = "Roboflow Parameter Update Service";
const INTERFACE_SERVICE = "Roboflow Workflow Interface Service";
const REFRESH_SERVICE = "Roboflow Workflow Refresh Service";

type WorkflowParameter = {
  name: string;
  default_value: unknown;
  kind: string[] | null;
  current_value: unknown;
};

type PipelineError = {
  event_type?: string;
  error_type?: string;
  message?: string;
  context?: string;
};

type PipelineStatus = {
  running: boolean;
  error: PipelineError | null;
};

type WorkflowInterface = {
  workspace_name: string;
  workflow_id: string;
  outputs: string[];
  parameters: WorkflowParameter[];
  pipeline?: PipelineStatus;
};

// How often to ask the backend whether the inference pipeline is still healthy
const HEALTH_POLL_MS = 4000;

type Payload = {
  api_key: string | null;
  workspace_name: string | null;
  workflow_id: string | null;
  workflow_parameters: Record<string, unknown> | null;
};

const inputStyle = css({
  padding: "2",
  border: "1px solid token(colors.gray.300)",
  borderRadius: "md",
  _focus: { borderColor: "token(colors.blue.400)", outline: "none" },
});

// Grey inline reload-emoji button (used for refresh and retry actions)
const iconButtonStyle = css({
  background: "none",
  border: "none",
  padding: "0",
  color: "gray.400",
  fontSize: "xl",
  lineHeight: "1",
  cursor: "pointer",
  _hover: { color: "gray.600" },
  _disabled: { opacity: 0.5, cursor: "not-allowed" },
});

/**
 * Service responses arrive as raw JSON bytes (DataView / ArrayBuffer),
 * decode them into an object. Returns null when decoding fails.
 */
function decodeServiceResponse(data: unknown): Record<string, unknown> | null {
  if (data === null || data === undefined) return null;
  try {
    if (typeof data === "string") return JSON.parse(data);
    if (data instanceof ArrayBuffer || ArrayBuffer.isView(data)) {
      return JSON.parse(new TextDecoder().decode(data as ArrayBufferView & ArrayBuffer));
    }
    if (typeof data === "object") return data as Record<string, unknown>;
  } catch (err) {
    console.error("Failed to decode service response:", err, data);
  }
  return null;
}

/** Serialize a parameter value for the text input */
function valueToText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

/**
 * Parse a text input back to a JSON value, using the parameter's
 * default value type as a hint. Falls back to the raw string.
 */
function textToValue(raw: string, defaultValue: unknown): unknown {
  const text = raw.trim();
  if (text === "") return null;
  // Even for string-typed parameters, an explicit JSON array/object should be
  // sent as such (e.g. custom_colors expects ["#FF0000"], not "#FF0000")
  if (typeof defaultValue === "string" && !/^[[{]/.test(text)) return text;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export function MessageInput() {
  const { notify } = useNotifications();
  const connection = useConnection();

  const [credentials, setCredentials] = useState({
    api_key: "",
    workspace_name: "",
    workflow_id: "",
  });
  const [workflowInterface, setWorkflowInterface] =
    useState<WorkflowInterface | null>(null);
  const [interfaceError, setInterfaceError] = useState(false);
  const [paramValues, setParamValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(
    null,
  );
  const lastErrorToastRef = useRef<string | null>(null);

  const applyInterface = useCallback((data: unknown) => {
    const iface = decodeServiceResponse(data) as
      | (Partial<WorkflowInterface> & { status?: string })
      | null;
    if (!iface || iface.status !== "ok" || !Array.isArray(iface.parameters)) {
      return false;
    }
    setWorkflowInterface(iface as WorkflowInterface);
    setInterfaceError(false);
    setPipelineStatus(iface.pipeline ?? null);
    const values: Record<string, string> = {};
    for (const param of iface.parameters) {
      values[param.name] = valueToText(param.current_value);
    }
    setParamValues(values);
    return true;
  }, []);

  const fetchInterface = useCallback(() => {
    setInterfaceError(false);
    connection.daiConnection?.postToService(
      // @ts-ignore - Custom service
      INTERFACE_SERVICE,
      {},
      (data: unknown) => {
        if (!applyInterface(data)) {
          console.warn("Unexpected workflow interface response:", data);
          setInterfaceError(true);
        }
      },
      10_000,
    );
  }, [connection, applyInterface]);

  // Fetch the workflow interface once connected
  useEffect(() => {
    if (!connection?.connected) return;
    fetchInterface();
  }, [connection?.connected, fetchInterface]);

  // Poll pipeline health. A single bad frame (e.g. a parameter value the
  // workflow rejects) kills the inference thread while the camera stream
  // keeps running - without this the UI would just show a frozen overlay.
  // Only the health state is updated here so the user's edits aren't lost.
  useEffect(() => {
    if (!connection?.connected) return;
    const id = window.setInterval(() => {
      if (submitting || refreshing) return;
      connection.daiConnection?.postToService(
        // @ts-ignore - Custom service
        INTERFACE_SERVICE,
        { quiet: true },
        (data: unknown) => {
          const iface = decodeServiceResponse(data) as
            | (Partial<WorkflowInterface> & { status?: string })
            | null;
          if (iface?.status === "ok" && iface.pipeline) {
            setPipelineStatus(iface.pipeline);
          }
        },
        HEALTH_POLL_MS,
      );
    }, HEALTH_POLL_MS);
    return () => window.clearInterval(id);
  }, [connection?.connected, connection, submitting, refreshing]);

  // Toast once per distinct pipeline error (the banner stays until fixed)
  useEffect(() => {
    const message = pipelineStatus?.error?.message;
    if (message) {
      if (lastErrorToastRef.current !== message) {
        lastErrorToastRef.current = message;
        notify(`Roboflow pipeline error: ${message}`, {
          type: "error",
          durationMs: 12000,
        });
      }
    } else {
      lastErrorToastRef.current = null;
    }
  }, [pipelineStatus, notify]);

  const handleRefresh = () => {
    if (!connection?.connected) {
      notify("Not connected to device. Unable to refresh.", { type: "error" });
      return;
    }
    setRefreshing(true);
    connection.daiConnection?.postToService(
      // @ts-ignore - Custom service
      REFRESH_SERVICE,
      {},
      (data: unknown) => {
        setRefreshing(false);
        if (applyInterface(data)) {
          notify("Workflow definition refreshed", {
            type: "success",
            durationMs: 3000,
          });
        } else {
          notify("Failed to refresh the workflow definition", {
            type: "error",
          });
          fetchInterface();
        }
      },
      120_000,
    );
  };

  const handleCredentialChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setCredentials((prev) => ({ ...prev, [name]: value }));
  };

  const handleParamChange = (name: string, value: string) => {
    setParamValues((prev) => ({ ...prev, [name]: value }));
  };

  const buildPayload = (): Payload => {
    const workflowChanged = credentials.workflow_id.trim() !== "";

    // When switching workflows, the old parameter values are meaningless -
    // let the backend fall back to the new workflow's defaults.
    let params: Record<string, unknown> | null = null;
    if (!workflowChanged && workflowInterface) {
      params = {};
      for (const param of workflowInterface.parameters) {
        const value = textToValue(
          paramValues[param.name] ?? "",
          param.default_value,
        );
        if (value !== null) params[param.name] = value;
      }
    }

    return {
      api_key: credentials.api_key.trim() || null,
      workspace_name: credentials.workspace_name.trim() || null,
      workflow_id: credentials.workflow_id.trim() || null,
      workflow_parameters: params,
    };
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!connection?.connected) {
      notify("Not connected to device. Unable to submit parameters.", {
        type: "error",
      });
      return;
    }

    const payload = buildPayload();
    console.log("Sending new Roboflow params to backend:", payload);
    setSubmitting(true);

    connection.daiConnection?.postToService(
      // @ts-ignore - Custom service
      UPDATE_SERVICE,
      payload,
      (data: unknown) => {
        setSubmitting(false);
        if (!applyInterface(data)) {
          // response missing/undecodable - re-fetch the interface instead
          fetchInterface();
        }
        notify("Roboflow params updated", { type: "success", durationMs: 3000 });
        setCredentials({ api_key: "", workspace_name: "", workflow_id: "" });
      },
      120_000,
    );
  };

  return (
    <section
      className={css({
        display: "flex",
        flexDirection: "column",
        gap: "md",
        width: "full",
        maxWidth: "md",
        textAlign: "left",
      })}
    >
      <header>
        <h2 className={css({ fontSize: "m", fontWeight: "semibold", mb: "1" })}>
          Adjust Roboflow Inference Parameters
        </h2>
        <div
          className={css({
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "sm",
          })}
        >
          {workflowInterface ? (
            <p className={css({ color: "gray.500", fontSize: "sm" })}>
              Active workflow: <b>{workflowInterface.workflow_id}</b> (workspace{" "}
              <b>{workflowInterface.workspace_name}</b>)
            </p>
          ) : interfaceError ? (
            <p className={css({ color: "red.500", fontSize: "sm" })}>
              Could not load the workflow interface.
            </p>
          ) : (
            <p className={css({ color: "gray.500", fontSize: "sm" })}>
              Loading workflow interface…
            </p>
          )}
          {/* Single reload button: retries the interface load when it failed,
              otherwise re-fetches the workflow definition and restarts */}
          <button
            type="button"
            onClick={workflowInterface ? handleRefresh : fetchInterface}
            disabled={refreshing || submitting}
            title={
              workflowInterface
                ? "Re-fetch the workflow definition from Roboflow and restart inference"
                : "Retry loading the workflow interface"
            }
            aria-label={
              workflowInterface
                ? "Refresh workflow definition"
                : "Retry loading the workflow interface"
            }
            className={iconButtonStyle}
            style={
              refreshing
                ? { animation: "rf-spin 1s linear infinite" }
                : undefined
            }
          >
            ↻
          </button>
        </div>
      </header>

      {pipelineStatus?.error ? (
        <div
          role="alert"
          className={css({
            backgroundColor: "red.50",
            border: "1px solid token(colors.red.300)",
            color: "red.900",
            borderRadius: "md",
            padding: "3",
            fontSize: "sm",
            wordBreak: "break-word",
          })}
        >
          <b>
            Inference pipeline{" "}
            {pipelineStatus.running ? "is failing" : "stopped"}
            {pipelineStatus.error.error_type
              ? ` (${pipelineStatus.error.error_type})`
              : ""}
            .
          </b>{" "}
          {pipelineStatus.error.message ?? "No error details available."}
          <p className={css({ mt: "1", color: "red.700" })}>
            Fix the workflow in the Roboflow builder and press ↻, or submit
            different parameter values.
          </p>
        </div>
      ) : pipelineStatus && !pipelineStatus.running ? (
        <p className={css({ color: "gray.500", fontSize: "sm" })}>
          Inference pipeline is starting…
        </p>
      ) : null}

      <form
        onSubmit={handleSubmit}
        className={css({
          display: "flex",
          flexDirection: "column",
          backgroundColor: "white",
          gap: "sm",
        })}
      >
        <details>
          <summary
            className={css({ fontWeight: "medium", cursor: "pointer", mb: "1" })}
          >
            Workflow selection
          </summary>
          <div
            className={css({
              display: "flex",
              flexDirection: "column",
              gap: "sm",
              paddingLeft: "2",
            })}
          >
            <label className={css({ display: "flex", flexDirection: "column" })}>
              <span className={css({ fontWeight: "medium" })}>API Key</span>
              <input
                type="text"
                name="api_key"
                value={credentials.api_key}
                onChange={handleCredentialChange}
                placeholder="Unchanged"
                className={inputStyle}
              />
            </label>

            <label className={css({ display: "flex", flexDirection: "column" })}>
              <span className={css({ fontWeight: "medium" })}>Workspace Name</span>
              <input
                type="text"
                name="workspace_name"
                value={credentials.workspace_name}
                onChange={handleCredentialChange}
                placeholder="Unchanged"
                className={inputStyle}
              />
            </label>

            <label className={css({ display: "flex", flexDirection: "column" })}>
              <span className={css({ fontWeight: "medium" })}>Workflow ID</span>
              <input
                type="text"
                name="workflow_id"
                value={credentials.workflow_id}
                onChange={handleCredentialChange}
                placeholder="Unchanged"
                className={inputStyle}
              />
            </label>
          </div>
        </details>

        <details open>
          <summary
            className={css({ fontWeight: "medium", cursor: "pointer", mb: "1" })}
          >
            Workflow parameters
          </summary>
          <div
            className={css({
              display: "flex",
              flexDirection: "column",
              gap: "sm",
              paddingLeft: "2",
            })}
          >
            {workflowInterface === null ? (
              <p className={css({ color: "gray.500" })}>
                {interfaceError
                  ? "Workflow parameters unavailable."
                  : "Loading workflow interface…"}
              </p>
            ) : workflowInterface.parameters.length === 0 ? (
              <p className={css({ color: "gray.500" })}>
                This workflow does not expose any parameters. Add a{" "}
                <i>Workflow Parameter</i> input in the Roboflow workflow builder
                and it will show up here.
              </p>
            ) : (
              workflowInterface.parameters.map((param) => (
                <label
                  key={param.name}
                  className={css({ display: "flex", flexDirection: "column" })}
                >
                  <span className={css({ fontWeight: "medium" })}>
                    {param.name}
                    {param.kind?.length ? (
                      <span
                        className={css({
                          color: "gray.400",
                          fontWeight: "normal",
                          fontSize: "sm",
                          ml: "1",
                        })}
                      >
                        ({param.kind.join(", ")})
                      </span>
                    ) : null}
                  </span>
                  <input
                    type={
                      typeof param.default_value === "number" ? "number" : "text"
                    }
                    step="any"
                    value={paramValues[param.name] ?? ""}
                    onChange={(e) => handleParamChange(param.name, e.target.value)}
                    placeholder={
                      param.default_value === null ||
                      param.default_value === undefined
                        ? "No default"
                        : `Default: ${valueToText(param.default_value)}`
                    }
                    className={inputStyle}
                  />
                </label>
              ))
            )}
          </div>
        </details>

        <Button
          type="submit"
          disabled={submitting || refreshing}
          className={css({
            mt: "sm",
            width: "full",
            justifyContent: "center",
          })}
        >
          {submitting ? "Applying…" : "Submit"}
        </Button>
      </form>
    </section>
  );
}
