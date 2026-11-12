import {
    Button,
    Flex,
    Popover,
    PopoverContent,
    PopoverTrigger,
    SettingsIcon,
    StyledText,
    SubHeader,
} from "@luxonis/common-fe-components";
import { useState } from "react";

import DetectionConfidenceField from "./DetectionConfidenceField";
import { useDetectionConfidenceThresholdDraft } from "./useDetectionConfidenceThreshold";

function DetectionSettingsButton() {
    const [open, setOpen] = useState(false);
    const { value, setValue, apply, error } =
        useDetectionConfidenceThresholdDraft();

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button
                    type="button"
                    variant={open ? "filled" : "outline"}
                    icon={SettingsIcon}
                    label="Detection settings"
                    disabled={value === undefined}
                />
            </PopoverTrigger>
            <PopoverContent align="end" width="xs">
                {value !== undefined ? (
                    <Flex direction="column" gap="sm" width="full">
                        <SubHeader text="Detection settings" />
                        <DetectionConfidenceField
                            value={value}
                            onChange={setValue}
                            onCommit={apply}
                        />
                        {error ? (
                            <StyledText
                                size="label"
                                color="error"
                                text={error.message}
                            />
                        ) : null}
                    </Flex>
                ) : null}
            </PopoverContent>
        </Popover>
    );
}

export default DetectionSettingsButton;
