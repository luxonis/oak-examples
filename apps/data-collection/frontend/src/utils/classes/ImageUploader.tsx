import { Button, Flex, useToast } from "@luxonis/common-fe-components";
import { css } from "../../../styled-system/css/css.mjs";
import { useState } from "react";
import { useDaiConnection } from "@luxonis/depthai-viewer-common";

type Props = {
    onDrawBBox?: () => void;
}

export function ImageUploader({ onDrawBBox }: Props) {
    const connection = useDaiConnection();
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const { toast } = useToast();

    const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file: File | null = event.target.files?.[0] || null;
        setSelectedFile(file);
        if (file) {
            toast({
                description: `Selected: ${file.name}`,
                colorVariant: "gray",
                duration: "default",
            });
        }
    };

    const handleUpload = () => {
        if (!selectedFile) {
            toast({
                description: "Please choose an image first",
                colorVariant: "warning",
                duration: "default",
            });            
            return;
        }
        if (!connection.connected) {
            toast({
                description: "Not connected to device. Unable to upload image.",
                colorVariant: "error",
                duration: "default",
            });
            return;
        }

        const reader = new FileReader();
        reader.onload = () => {
            const fileData = reader.result;

            console.log("Uploading image to backend:", selectedFile.name);
            const sizeKb = Math.max(1, Math.round((selectedFile.size || 0) / 1024));
            toast({
                description: `Uploading ${selectedFile.name} (${sizeKb} KB)…`,
                colorVariant: "gray",
                duration: "default",
            });

            // @ts-ignore - Custom service
            (connection as any).daiConnection?.postToService(
                "Image Upload Service",
                {
                    filename: selectedFile.name,
                    type: selectedFile.type,
                    data: fileData
                },
                (resp: any) => {
                    console.log("[ImageUpload] Service ack:", resp);
                    toast({
                        description: `Image uploaded: ${selectedFile.name}`,
                        colorVariant: "success",
                        duration: "long",
                    });
                }
            );
        };

        reader.readAsDataURL(selectedFile);
    };

    return (
        <div className={css({ display: "flex", flexDirection: "column", gap: "sm" })}>
            <h3 className={css({ fontWeight: "semibold" })}>Update Classes with Image Input:</h3>
            <span className={css({ color: 'gray.600', fontSize: 'sm' })}>Important: reset view before drawing a bounding box</span>

            {/* Clickable file selection area */}
            <label
                htmlFor="fileInput"
                className={css({
                    border: "2px dashed",
                    borderColor: "gray.400",
                    borderRadius: "md",
                    padding: "md",
                    textAlign: "center",
                    cursor: "pointer",
                    backgroundColor: "gray.50",
                    _hover: { backgroundColor: "gray.100" },
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
            />

            {/* Upload / Draw buttons */}
            <Flex direction="row" gap="sm" alignItems="center">
                <Button onClick={handleUpload}>Upload Image</Button>
                <span className={css({ color: 'gray.500' })}>OR</span>
                <Button
                    variant="outline"
                    onClick={() => {
                        console.log("[BBox] Button clicked: enabling drawing overlay");
                        onDrawBBox?.();
                        toast({
                            description: "Drawing mode enabled. Drag on the stream to draw a box.",
                            colorVariant: "gray",
                            duration: "long",
                        });
                    }}
                >
                    Draw bounding box
                </Button>
            </Flex>
        </div>
    );
}
