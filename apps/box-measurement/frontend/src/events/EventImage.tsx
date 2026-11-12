import { useEventFile } from "./useEventFile";
import { useObjectUrl } from "./useObjectUrl";

type EventImageProps = Omit<
    React.ImgHTMLAttributes<HTMLImageElement>,
    "src"
> & {
    path: string;
};

export function EventImage({ path, ...imgProps }: EventImageProps) {
    const { eventFileQuery } = useEventFile(path);
    const imageUrl = useObjectUrl(eventFileQuery.data, "image/jpeg");

    if (!imageUrl) {
        return null;
    }

    return <img src={imageUrl} {...imgProps} />;
}
