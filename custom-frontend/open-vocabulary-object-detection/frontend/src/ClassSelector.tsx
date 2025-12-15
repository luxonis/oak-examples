import { Flex, Button, Input } from "@luxonis/common-fe-components";
import { css } from "../styled-system/css/css.mjs";
import { useRef, useState } from "react";
import { useDaiConnection } from "@luxonis/depthai-viewer-common";
import { useNotifications } from "./Notifications.tsx";

interface ClassSelectorProps {
  initialClasses?: string[];
  onClassesUpdated?: (classes: string[]) => void;
}

export function ClassSelector({ initialClasses = [], onClassesUpdated }: ClassSelectorProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const connection = useDaiConnection();
  const [selectedClasses, setSelectedClasses] = useState<string[]>(initialClasses);
  const { notify } = useNotifications();

  const handleSendMessage = () => {
    if (inputRef.current) {
      const value = inputRef.current.value;
      const updatedClasses = value
        .split(",")
        .map((c: string) => c.trim())
        .filter(Boolean);

      if (updatedClasses.length === 0) {
        notify("Please enter at least one class (comma separated).", {
          type: "warning",
          durationMs: 5000,
        });
        return;
      }
      if (!connection.connected) {
        notify("Not connected to device. Unable to update classes.", {
          type: "error",
        });
        return;
      }

      console.log("Sending new class list to backend:", updatedClasses);
      notify(
        `Updating ${updatedClasses.length} class${
          updatedClasses.length > 1 ? "es" : ""
        }…`,
        { type: "info" }
      );

      connection.daiConnection?.postToService(
        // @ts-ignore - Custom service
        "Class Update Service",
        updatedClasses,
        () => {
          console.log("Backend acknowledged class update");
          setSelectedClasses(updatedClasses);
          notify(`Classes updated (${updatedClasses.join(", ")})`, {
            type: "success",
            durationMs: 6000,
          });
          onClassesUpdated?.(updatedClasses);
        }
      );

      inputRef.current.value = "";
    }
  };

  return (
    <div className={css({ display: "flex", flexDirection: "column", gap: "sm" })}>
      {/* Class List Display */}
      <h3 className={css({ fontWeight: "semibold" })}>
        Update Classes with Text Input:
      </h3>

      <div
        className={css({
          maxHeight: "150px",
          overflowY: "auto",
          border: "1px solid token(colors.border.subtle)",
          borderRadius: "md",
          padding: "sm",
          backgroundColor: "token(colors.bg.surface)",
        })}
      >
        {selectedClasses.length > 0 ? (
          <ul className={css({ listStyle: "disc", pl: "lg", m: 0 })}>
            {selectedClasses.map((cls, i) => (
              <li key={i}>{cls}</li>
            ))}
          </ul>
        ) : (
          <p className={css({ color: "gray.600", fontSize: "sm" })}>No classes selected.</p>
        )}
      </div>

      {/* Input + Button */}
      <Flex direction="row" gap="sm" alignItems="center">
        <Input type="text" placeholder="person,chair,TV" ref={inputRef} />
        <Button onClick={handleSendMessage}>Update&nbsp;Classes</Button>
      </Flex>
    </div>
  );
}