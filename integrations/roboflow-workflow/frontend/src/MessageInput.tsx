// MessageInput.tsx
import React, { useState } from "react";
import { css } from "../styled-system/css/css.mjs";
import { useNotifications } from "./Notifications";
import { useConnection } from "@luxonis/depthai-viewer-common";
import { Button } from "@luxonis/common-fe-components";

// Adjust to match the backend service registered in your pipeline
const SERVICE_NAME = "Roboflow Parameter Update Service";

type Payload = {
  api_key: string | null;
  workspace_name: string | null;
  workflow_id: string | null;
  workflow_parameters: Record<string, unknown> | null;
};

export function MessageInput() {
  const { notify } = useNotifications();
  const connection = useConnection();
  const initialFormState = {
    api_key: "",
    workspace_name: "",
    workflow_id: "",
    workflow_parameters: "", // unchanged => null
  };
  const [formData, setFormData] = useState({
    ...initialFormState,
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const buildPayload = (): Payload | null => {
    // Parse JSON or return null if unchanged/empty
    let params: Record<string, unknown> | null = null;
    const raw = formData.workflow_parameters.trim();
    if (raw) {
      try {
        params = JSON.parse(raw);
      } catch {
        notify("Invalid JSON in Workflow Parameters", { type: "error" });
        return null;
      }
    }

    return {
      api_key: formData.api_key.trim() || null,
      workspace_name: formData.workspace_name.trim() || null,
      workflow_id: formData.workflow_id.trim() || null,
      workflow_parameters: params,
    };
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!connection?.connected) {
      notify("Not connected to device. Unable to submit parameters.", { type: "error" });
      return;
    }

    const payload = buildPayload();
    if (!payload) return;

    console.log('Sending new Roboflow params to backend:', payload);

    connection.daiConnection?.postToService(
        // @ts-ignore - Custom service
        SERVICE_NAME,
        payload,
        () => {
            console.log('Backend acknowledged class update');
            notify(`Roboflow params updated`, { type: 'success', durationMs: 3000 });
            setFormData(initialFormState);
        }
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
        <p>
          You can adjust the Roboflow inference pipeline parameters using the fields below. All fields are optional.
        </p>
      </header>

      <form
        onSubmit={handleSubmit}
        className={css({
          display: "flex",
          flexDirection: "column",
          backgroundColor: "white",
          gap: "sm",
        })}
      >
        <label className={css({ display: "flex", flexDirection: "column" })}>
          <span className={css({ fontWeight: "medium" })}>API Key</span>
          <input
            type="text"
            name="api_key"
            value={formData.api_key}
            onChange={handleChange}
            placeholder="Optional"
            className={css({
              padding: "2",
              border: "1px solid token(colors.gray.300)",
              borderRadius: "md",
              _focus: { borderColor: "token(colors.blue.400)", outline: "none" },
            })}
          />
        </label>

        <label className={css({ display: "flex", flexDirection: "column" })}>
          <span className={css({ fontWeight: "medium" })}>Workspace Name</span>
          <input
            type="text"
            name="workspace_name"
            value={formData.workspace_name}
            onChange={handleChange}
            placeholder="Optional"
            className={css({
              padding: "2",
              border: "1px solid token(colors.gray.300)",
              borderRadius: "md",
              _focus: { borderColor: "token(colors.blue.400)", outline: "none" },
            })}
          />
        </label>

        <label className={css({ display: "flex", flexDirection: "column" })}>
          <span className={css({ fontWeight: "medium" })}>Workflow ID</span>
          <input
            type="text"
            name="workflow_id"
            value={formData.workflow_id}
            onChange={handleChange}
            placeholder="Optional"
            className={css({
              padding: "2",
              border: "1px solid token(colors.gray.300)",
              borderRadius: "md",
              _focus: { borderColor: "token(colors.blue.400)", outline: "none" },
            })}
          />
        </label>

        <label className={css({ display: "flex", flexDirection: "column" })}>
          <span className={css({ fontWeight: "medium" })}>Workflow Parameters (JSON)</span>
          <textarea
            name="workflow_parameters"
            value={formData.workflow_parameters}
            onChange={handleChange}
            rows={5}
            placeholder='Optional — e.g. { "param1": "value" }'
            className={css({
              padding: "2",
              border: "1px solid token(colors.gray.300)",
              borderRadius: "md",
              fontFamily: "monospace",
              _focus: { borderColor: "token(colors.blue.400)", outline: "none" },
            })}
          />
        </label>

        <Button
          type="submit"
          className={css({
            mt: "sm",
            width: "full",
            justifyContent: "center",
          })}
        >
          Submit
        </Button>
      </form>
    </section>
  );
}
