import { Button } from "@luxonis/common-fe-components";
import { css } from "../styled-system/css/css.mjs";
import { useState } from "react";
import { useConnection } from "@luxonis/depthai-viewer-common";

export function ImageUploader() {
    const connection = useConnection();
    const [selectedFile, setSelectedFile] = useState<File | null>(null);

    const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0] || null;
        setSelectedFile(file);
    };

    const handleUpload = () => {
        if (!selectedFile) {
            return;
        }

        const reader = new FileReader();
        reader.onload = () => {
            const fileData = reader.result;

            console.log("Uploading image to backend:", selectedFile.name);

            // @ts-ignore - Custom service
            connection.daiConnection?.postToService(
                "Image Upload Service",
                {
                    filename: selectedFile.name,
                    type: selectedFile.type,
                    data: fileData
                }
            );
        };

        reader.readAsDataURL(selectedFile);
    };

    return (
        <div className={css({ display: "flex", flexDirection: "column", gap: "sm" })}>
            <h3 className={css({ fontWeight: "semibold" })}>Update Classes with Image Input:</h3>

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

            {/* Upload button */}
            <Button onClick={handleUpload}>Upload Image</Button>
        </div>
    );
}
