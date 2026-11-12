import {
    Flex,
    Label,
    Slider,
} from "@luxonis/common-fe-components";

type DetectionConfidenceFieldProps = {
    value: number;
    onChange: (value: number) => void;
    onCommit: (value: number) => void;
    disabled?: boolean;
};

function DetectionConfidenceField({
    value,
    onChange,
    onCommit,
    disabled = false,
}: DetectionConfidenceFieldProps) {
    return (
        <Flex direction="column" gap="xs" width="full">
            <Flex justifyContent="space-between" alignItems="center" width="full">
                <Label
                    text="Detection confidence threshold"
                    color="normal"
                    weight="medium"
                />
                <Label text={value.toFixed(2)} />
            </Flex>
            <Slider
                aria-label="Minimum detection confidence"
                min={0}
                max={1}
                step={0.01}
                value={value}
                onChange={onChange}
                onValueCommit={([committed]) => onCommit(committed)}
                disabled={disabled}
                thumbSize="sm"
            />
        </Flex>
    );
}

export default DetectionConfidenceField;
