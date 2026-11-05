import { useEffect, useMemo } from "react";

import { useEventFile } from "./useEventFile";

type EventImageProps = Omit<
    React.ImgHTMLAttributes<HTMLImageElement>,
    "src"
> & {
    path: string;
};

export function EventImage({ path, ...imgProps }: EventImageProps) {
    const { eventFileQuery } = useEventFile(path);

    const imageUrl = useMemo(() => {
        if (!eventFileQuery.data) {
            return null;
        }

        const bytes = new Uint8Array(eventFileQuery.data.byteLength);
        bytes.set(
            new Uint8Array(
                eventFileQuery.data.buffer,
                eventFileQuery.data.byteOffset,
                eventFileQuery.data.byteLength,
            ),
        );

        return URL.createObjectURL(
            new Blob([bytes], { type: "image/jpeg" }),
        );
    }, [eventFileQuery.data]);

    useEffect(() => {
        if (!imageUrl) {
            return;
        }

        return () => {
            URL.revokeObjectURL(imageUrl);
        };
    }, [imageUrl]);

    if (!imageUrl) {
        return null;
    }

    return <img src={imageUrl} {...imgProps} />;
}
