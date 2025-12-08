import { Button, Flex } from "@luxonis/common-fe-components";
import { css } from "../styled-system/css/css.mjs";
import { useState } from "react";
import { useConnection } from "@luxonis/depthai-viewer-common";
import { useNotifications } from "./Notifications.tsx";


type Props = {
    onDrawBBox?: () => void;
    getNextLabel?: () => string | null;
    onImagePromptAdded?: (label: string) => void;
    maxReached?: boolean;
}

export function ImageUploader({ onDrawBBox, getNextLabel, onImagePromptAdded, maxReached }: Props) {
    const connection = useConnection();
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const { notify } = useNotifications();

    const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file: File | null = event.target.files?.[0] || null;
        setSelectedFile(file);
        if (file) {
            notify(`Selected: ${file.name}`, { type: 'info', durationMs: 2000 });
        }
    };

    const handleUpload = () => {
        if (maxReached) {
            notify('Maximum image prompts reached. Delete some before adding more.', { type: 'warning', durationMs: 6000 });
            return;
        }
        if (!selectedFile) {
            notify('Please choose an image first', { type: 'warning' });
            return;
        }
        if (!connection.connected) {
            notify('Not connected to device. Unable to upload image.', { type: 'error' });
            return;
        }

        // Derive label from filename (without extension); fallback to provided generator
        const dotIndex = selectedFile.name.lastIndexOf('.');
        const baseName = (dotIndex > 0 ? selectedFile.name.slice(0, dotIndex) : selectedFile.name).trim();
        const fallback = getNextLabel?.();
        const label = (baseName || fallback || '').trim();
        if (!label) {
            return;
        }

        const reader = new FileReader();
        reader.onload = () => {
            const fileData = reader.result;

            console.log("Uploading image to backend:", selectedFile.name);
            const sizeKb = Math.max(1, Math.round((selectedFile.size || 0) / 1024));
            notify(`Uploading ${selectedFile.name} (${sizeKb} KB)…`, { type: 'info' });

            // @ts-ignore - Custom service
            (connection as any).daiConnection?.postToService(
                "Image Upload Service",
                {
                    filename: selectedFile.name,
                    type: selectedFile.type,
                    data: fileData,
                    label
                },
                (resp: any) => {
                    console.log("[ImageUpload] Service ack:", resp);
                    notify(`Image uploaded: ${selectedFile.name}`, { type: 'success', durationMs: 6000 });
                    onImagePromptAdded?.(label);
                }
            );
        };

        reader.readAsDataURL(selectedFile);
    };

    return (
        <div className={css({ display: "flex", flexDirection: "column", gap: "sm" })}>
            <h3 className={css({ fontWeight: "semibold" })}>Update Classes with Image Input:</h3>
            <span className={css({ color: 'gray.600', fontSize: 'sm' })}>Important: reset view before drawing a bounding box</span>
            {maxReached && (
                <span className={css({ color: 'red.600', fontSize: 'sm' })}>
                    Maximum number of image prompts reached. Please delete or reset image prompts to add more.
                </span>
            )}

            {/* Clickable file selection area */}
            <label
                htmlFor="fileInput"
                className={css({
                    border: "2px dashed",
                    borderColor: "gray.400",
                    borderRadius: "md",
                    padding: "md",
                    textAlign: "center",
                    cursor: maxReached ? "not-allowed" : "pointer",
                    backgroundColor: "gray.50",
                    _hover: { backgroundColor: maxReached ? "gray.50" : "gray.100" },
                })}
            >
                {selectedFile ? selectedFile.name : "Click here to choose an image file"}
            </label>

            {/* Hidden file input */}
            <input
                id="fileInput"
                type="file"
                accept="image/*"
                onChange={handleFileSelect}
                style={{ display: "none" }}
                disabled={maxReached}
            />

            {/* Upload / Draw buttons */}
            <Flex direction="row" gap="sm" alignItems="center">
                <Button onClick={handleUpload} disabled={maxReached}>Upload Image</Button>
                <span className={css({ color: 'gray.500' })}>OR</span>
                <Button
                    variant="outline"
                    onClick={() => {
                        console.log("[BBox] Button clicked: enabling drawing overlay");
                        onDrawBBox?.();
                        notify('Drawing mode enabled. Drag on the stream to draw a box.', { type: 'info', durationMs: 6000 });
                    }}
                    disabled={maxReached}
                >
                    Draw bounding box
                </Button>
            </Flex>
        </div>
    );
}
