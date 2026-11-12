import {
    Alert,
    Button,
    Card,
    Checkbox,
    CircleLoader,
    Flex,
    Form,
    FormField,
    Grid,
    Input,
    LightSubLabel,
    ReloadIcon,
    Select,
    SettingsIcon,
    SubHeader,
    SubLabel,
    useForm,
    type UseFormReturn,
} from "@luxonis/common-fe-components";
import { useState } from "react";

import {
    settingsSchema,
    type Settings,
    type SettingsFormValues,
} from "./settingsSchema";
import { useSettings } from "./useSettings";
import { useStorageInfo, type StorageInfo } from "./useStorageInfo";

type UpdateSettingsMutation = ReturnType<
    typeof useSettings
>["updateSettingsMutation"];

const BYTES_PER_GB = 1024 ** 3;

function formatGb(bytes: number): string {
    return `${(bytes / BYTES_PER_GB).toFixed(1)} GB`;
}

type ChunkLengthUnit = "seconds" | "minutes";

const CHUNK_LENGTH_UNITS: Record<ChunkLengthUnit, number> = {
    seconds: 1,
    minutes: 60,
};

function ChunkLengthField(props: {
    form: UseFormReturn<SettingsFormValues>;
    disabled: boolean;
}) {
    const [unit, setUnit] = useState<ChunkLengthUnit>("minutes");
    const multiplier = CHUNK_LENGTH_UNITS[unit];

    return (
        <FormField
            form={props.form}
            name="continuous_recording_chunk_length_sec"
            label="Recording chunk length"
            fullWidth
            render={(field) => (
                <Grid gap="sm" columns={{ base: 1, md: 2 }}>
                    <Input
                        {...field}
                        value={Number(field.value) / multiplier}
                        type="number"
                        min={1}
                        step="1"
                        autoComplete="off"
                        disabled={props.disabled}
                        onChange={(event) => {
                            field.onChange(Number(event.target.value) * multiplier);
                        }}
                    />
                    <Select
                        value={unit}
                        disabled={props.disabled}
                        onChange={(value) => {
                            setUnit(value as ChunkLengthUnit);
                        }}
                        items={[
                            { value: "seconds", component: "Seconds" },
                            { value: "minutes", component: "Minutes" },
                        ]}
                    />
                </Grid>
            )}
        />
    );
}

function StorageSummary(props: { storage: StorageInfo }) {
    const { storage } = props;
    return (
        <LightSubLabel
            text={
                <>
                    Device storage:{" "}
                    <strong>{formatGb(storage.free_bytes)} free</strong> of{" "}
                    {formatGb(storage.total_bytes)} · footage{" "}
                    {formatGb(storage.recordings_bytes)}
                </>
            }
        />
    );
}

function SettingsFormInner(props: {
    settings: Settings;
    storage: StorageInfo | undefined;
    updateSettingsMutation: UpdateSettingsMutation;
}) {
    const form = useForm(
        settingsSchema as never,
        props.settings,
        "all",
    ) as UseFormReturn<SettingsFormValues>;

    const isPending = props.updateSettingsMutation.isPending;
    const isDisabled =
        isPending || !form.formState.isDirty || !form.formState.isValid;

    const handleApply = (values: SettingsFormValues) => {
        props.updateSettingsMutation.reset();
        props.updateSettingsMutation.mutate(values);
    };

    const handleDiscard = () => {
        props.updateSettingsMutation.reset();
    };

    return (
        <Flex direction="column" gap="sm" width="full">
            {props.updateSettingsMutation.error ? (
                <Alert
                    variant="light"
                    colorVariant="error"
                    title="Could not apply settings"
                    description={props.updateSettingsMutation.error.message}
                />
            ) : null}

            {props.storage ? <StorageSummary storage={props.storage} /> : null}

            <Form
                form={form}
                onSubmit={handleApply}
                errorToast={false}
                submitLabel={isPending ? "Applying..." : "Apply settings"}
                submitIcon={isPending ? ReloadIcon : SettingsIcon}
                canDiscard
                onReset={handleDiscard}
                disabled={() => isDisabled}
            >
                <Grid gap="sm" columns={{ base: 1, lg: 2 }}>
                    <Card
                        title="Footage"
                        subtitle="Continuous RGB recording."
                        height="full"
                    >
                        <Grid gap="sm">
                            <FormField
                                form={form}
                                name="continuous_recording_enabled"
                                label="Continuous recording"
                                fullWidth
                                render={(field) => (
                                    <Checkbox
                                        {...field}
                                        id={field.name}
                                        label="Record continuous footage"
                                        disabled={isPending}
                                    />
                                )}
                            />
                            <ChunkLengthField form={form} disabled={isPending} />
                            <FormField
                                form={form}
                                name="continuous_recording_max_storage_gb"
                                label="Max footage storage (GB)"
                                fullWidth
                                render={(field) => (
                                    <Input
                                        {...field}
                                        type="number"
                                        min={1}
                                        step="1"
                                        autoComplete="off"
                                        disabled={isPending}
                                    />
                                )}
                            />
                            <SubLabel text="Footage is limited by this cap or by available disk space." />
                        </Grid>
                    </Card>
                </Grid>
                <Flex width="full" justifyContent="flex-end">
                    <SubLabel text="Applying settings briefly restarts the camera pipeline." />
                </Flex>
            </Form>
        </Flex>
    );
}

function SettingsForm() {
    const { settingsQuery, updateSettingsMutation } = useSettings();
    const { storageInfoQuery } = useStorageInfo();

    if (settingsQuery.error) {
        return (
            <Alert
                variant="light"
                colorVariant="error"
                title="Could not load settings"
                description={settingsQuery.error.message}
                actions={
                    <Button
                        type="button"
                        variant="outline"
                        colorVariant="white"
                        label="Retry"
                        onClick={() => {
                            settingsQuery.refetch();
                        }}
                    />
                }
            />
        );
    }

    if (!settingsQuery.data) {
        return (
            <Card>
                <Flex
                    direction="column"
                    gap="xs"
                    alignItems="center"
                    p="sm"
                    justifyContent="center"
                >
                    <CircleLoader mb="md" />
                    <SubHeader text="Loading settings" />
                    <SubLabel text="Waiting for the settings service to become available." />
                </Flex>
            </Card>
        );
    }

    return (
        <SettingsFormInner
            settings={settingsQuery.data}
            storage={storageInfoQuery.data}
            updateSettingsMutation={updateSettingsMutation}
        />
    );
}

export default SettingsForm;
