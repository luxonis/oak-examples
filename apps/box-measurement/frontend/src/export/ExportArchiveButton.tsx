import { Button } from "@luxonis/common-fe-components";

import type { EventExportStatus } from "./useEventExport";

type ExportArchiveButtonProps = {
    status: EventExportStatus | undefined;
    isStatusPending: boolean;
    isCreatePending: boolean;
    isDeletePending: boolean;
    onCreate: () => void;
};

export function ExportArchiveButton({
    status,
    isStatusPending,
    isCreatePending,
    isDeletePending,
    onCreate,
}: ExportArchiveButtonProps) {
    const isPreparing = status?.state === "preparing" || isCreatePending;
    const label = isDeletePending
        ? "Deleting archive..."
        : isPreparing
          ? "Creating archive..."
          : isStatusPending
            ? "Loading export..."
            : status?.archive
              ? "Create new archive"
              : "Create archive";

    return (
        <Button
            type="button"
            variant="filled"
            label={label}
            disabled={isPreparing || isDeletePending || isStatusPending}
            onClick={onCreate}
        />
    );
}
