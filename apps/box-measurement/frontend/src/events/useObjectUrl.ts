import { useEffect, useMemo } from "react";

// Wraps binary data in a Blob and exposes it as an object URL, revoking it when
// the data changes or the component unmounts.
export function useObjectUrl(
    data: ArrayBufferView | null | undefined,
    mimeType: string,
) {
    const url = useMemo(() => {
        if (!data || data.byteLength === 0) {
            return null;
        }

        const view = new Uint8Array(
            data.buffer as ArrayBuffer,
            data.byteOffset,
            data.byteLength,
        );
        return URL.createObjectURL(new Blob([view], { type: mimeType }));
    }, [data, mimeType]);

    useEffect(() => {
        if (!url) {
            return;
        }

        return () => {
            URL.revokeObjectURL(url);
        };
    }, [url]);

    return url;
}
