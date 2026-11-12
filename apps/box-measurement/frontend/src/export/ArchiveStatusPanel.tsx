import {
    Alert,
    Button,
    Card,
    CircleLoader,
    Flex,
    LightSubLabel,
    NormalText,
    StyledText,
    WarningIcon,
} from "@luxonis/common-fe-components";
import { useState } from "react";

import { formatBytes } from "./exportFormat";
import type { EventExportStatus } from "./useEventExport";

const timestampFormatter = new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
});

type CopyState = "idle" | "copied" | "failed";

type ArchiveStatusPanelProps = {
    status: EventExportStatus;
    isDeletePending: boolean;
    onDelete: () => void;
};

export function ArchiveStatusPanel({
    status,
    isDeletePending,
    onDelete,
}: ArchiveStatusPanelProps) {
    // Keyed by command, so a new archive starts back at "idle"
    const [copied, setCopied] = useState<{
        command: string;
        state: CopyState;
    } | null>(null);

    if (status.state === "absent") {
        return null;
    }

    if (status.state === "preparing") {
        const progress =
            status.total_event_count > 0
                ? `${status.processed_event_count} of ${status.total_event_count} events added`
                : "Collecting events, settings, support plane and logs...";

        return (
            <Card fullWidth>
                <Flex alignItems="center" gap="sm" py="sm">
                    <CircleLoader />
                    <Flex direction="column" gap="xs">
                        <StyledText
                            text="Creating export archive..."
                            size="label"
                            color="normal"
                            weight="bold"
                        />
                        <LightSubLabel text={progress} />
                    </Flex>
                </Flex>
            </Card>
        );
    }

    const archive = status.archive;
    const copyState: CopyState =
        archive && copied?.command === archive.scp_command
            ? copied.state
            : "idle";

    const copyCommand = () => {
        if (!archive) {
            return;
        }
        const command = archive.scp_command;
        // navigator.clipboard is undefined on plain-http pages
        if (!navigator.clipboard) {
            setCopied({ command, state: "failed" });
            return;
        }
        void navigator.clipboard
            .writeText(command)
            .then(() => setCopied({ command, state: "copied" }))
            .catch(() => setCopied({ command, state: "failed" }));
    };

    return (
        <Flex direction="column" gap="sm">
            {status.state === "failed" ? (
                <Alert
                    variant="light"
                    colorVariant="error"
                    icon={WarningIcon}
                    title="Unable to create export archive"
                    description={
                        status.failure_message ?? "The export operation failed."
                    }
                />
            ) : null}

            {archive?.warnings.map((warning, index) => (
                <Alert
                    key={`${warning.code}-${index}`}
                    variant="light"
                    colorVariant="warning"
                    icon={WarningIcon}
                    title="Export archive has incomplete logs"
                    description={`${warning.message}${warning.file ? ` File: ${warning.file}.` : ""} ${warning.suggested_action}`}
                />
            ))}

            {archive ? (
                <Card fullWidth>
                    <Flex
                        alignItems="center"
                        justifyContent="space-between"
                        gap="md"
                        flexWrap="wrap"
                        py="sm"
                    >
                        <Flex direction="column" gap="xs" minWidth={0}>
                            <StyledText
                                text={archive.filename}
                                size="label"
                                color="normal"
                                weight="bold"
                                break="none"
                            />
                            <LightSubLabel
                                text={`${formatBytes(archive.byte_size)} · ${archive.event_count.toLocaleString()} events · created ${timestampFormatter.format(archive.created_at)}`}
                            />
                            <NormalText text="Run this command on your computer to download the archive:" />
                            <code
                                style={{
                                    fontSize: "0.75rem",
                                    overflowWrap: "anywhere",
                                }}
                            >
                                {archive.scp_command}
                            </code>
                            {copyState === "failed" ? (
                                <NormalText text="Could not copy the command. Select it manually." />
                            ) : null}
                        </Flex>

                        <Flex gap="xs" flexWrap="wrap">
                            <Button
                                type="button"
                                variant="outline"
                                label={
                                    copyState === "copied"
                                        ? "Command copied"
                                        : "Copy command"
                                }
                                onClick={copyCommand}
                            />
                            <Button
                                type="button"
                                variant="outline"
                                label={
                                    isDeletePending
                                        ? "Deleting archive..."
                                        : "Delete archive"
                                }
                                disabled={isDeletePending}
                                onClick={onDelete}
                            />
                        </Flex>
                    </Flex>
                </Card>
            ) : null}
        </Flex>
    );
}
