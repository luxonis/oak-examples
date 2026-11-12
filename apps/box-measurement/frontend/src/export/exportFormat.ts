const BYTE_UNITS = ["KB", "MB", "GB", "TB"];

export function formatBytes(value: number) {
    if (value < 1_024) {
        return `${value} B`;
    }

    let size = value / 1_024;
    let unitIndex = 0;
    while (size >= 1_024 && unitIndex < BYTE_UNITS.length - 1) {
        size /= 1_024;
        unitIndex += 1;
    }

    return `${size.toFixed(size >= 10 ? 0 : 1)} ${BYTE_UNITS[unitIndex]}`;
}
