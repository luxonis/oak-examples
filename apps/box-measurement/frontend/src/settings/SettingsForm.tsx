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
    ReloadIcon,
    SettingsIcon,
    SubHeader,
    SubLabel,
    useForm,
    type UseFormReturn,
} from "@luxonis/common-fe-components";

import {
    settingsSchema,
    type Settings,
    type SettingsFormValues,
} from "./settingsSchema";
import { useSettings } from "./useSettings";

type UpdateSettingsMutation = ReturnType<
    typeof useSettings
>["updateSettingsMutation"];

function SettingsFormInner(props: {
    settings: Settings;
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
                        title="Events"
                        subtitle="Capture of measurement events."
                        height="full"
                    >
                        <Grid gap="sm">
                            <FormField
                                form={form}
                                name="event_saving_enabled"
                                label="Event capture"
                                fullWidth
                                render={(field) => (
                                    <Checkbox
                                        {...field}
                                        id={field.name}
                                        label="Save measurement events"
                                        disabled={isPending}
                                    />
                                )}
                            />
                            <FormField
                                form={form}
                                name="save_failed_events"
                                label="Failed attempts"
                                fullWidth
                                render={(field) => (
                                    <Checkbox
                                        {...field}
                                        id={field.name}
                                        label="Save failed measurement attempts"
                                        disabled={isPending}
                                    />
                                )}
                            />
                            <FormField
                                form={form}
                                name="event_storage_max_gb"
                                label="Max event storage (GB)"
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
            updateSettingsMutation={updateSettingsMutation}
        />
    );
}

export default SettingsForm;
