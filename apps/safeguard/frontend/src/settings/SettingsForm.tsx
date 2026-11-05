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
    GridItem,
    Input,
    ReloadIcon,
    Select,
    SettingsIcon,
    SubHeader,
    SubLabel,
    Tooltip,
    useForm,
    type UseFormReturn,
} from "@luxonis/common-fe-components";
import {
    settingsSchema,
    type Settings,
    type SettingsFormValues,
} from "./settingsSchema";
import { useSettings } from "./useSettings";

type ZoneFieldName = "danger_roi" | "warning_roi";
type UpdateSettingsMutation = ReturnType<
    typeof useSettings
>["updateSettingsMutation"];

function SectionHeading({ title, description }: { title: string; description: string }) {
    return (
        <div className="settings-section-heading">
            <h2>{title}</h2>
            <p>{description}</p>
        </div>
    );
}

function ZoneFields(props: {
    form: UseFormReturn<SettingsFormValues>;
    name: ZoneFieldName;
    label: string;
    disabled: boolean;
}) {
    return (
        <Card
            title={<SectionHeading title={props.label} description="Distance and horizontal bounds relative to the camera center." />}
            titleSeparator={false}
            cardStyles="safeguard-settings-card"
            fullWidth
            height="full"
        >
            <Flex direction="column" gap="sm">
                <SubLabel text="Negative x is left of center. Positive x is right of center." />
                <Grid
                    gap="sm"
                    columns={{
                        base: 1,
                        md: 3,
                    }}
                >
                    <FormField
                        form={props.form}
                        name={`${props.name}.distance_mm`}
                        label="Distance (mm)"
                        fullWidth
                        render={(field) => (
                            <Input
                                {...field}
                                type="number"
                                min={0}
                                step="1"
                                autoComplete="off"
                                disabled={props.disabled}
                            />
                        )}
                    />
                    <FormField
                        form={props.form}
                        name={`${props.name}.x_min_mm`}
                        label="X min (mm)"
                        fullWidth
                        render={(field) => (
                            <Input
                                {...field}
                                type="number"
                                step="1"
                                autoComplete="off"
                                disabled={props.disabled}
                            />
                        )}
                    />
                    <FormField
                        form={props.form}
                        name={`${props.name}.x_max_mm`}
                        label="X max (mm)"
                        fullWidth
                        render={(field) => (
                            <Input
                                {...field}
                                type="number"
                                step="1"
                                autoComplete="off"
                                disabled={props.disabled}
                            />
                        )}
                    />
                </Grid>
            </Flex>
        </Card>
    );
}

function SettingsFormInner(props: {
    settings: Settings;
    updateSettingsMutation: UpdateSettingsMutation;
}) {
    const form = useForm(
        settingsSchema as never,
        props.settings,
        "all",
    ) as UseFormReturn<SettingsFormValues>;

    const isDisabled =
        props.updateSettingsMutation.isPending ||
        !form.formState.isDirty ||
        !form.formState.isValid;

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
                submitLabel={
                    props.updateSettingsMutation.isPending
                        ? "Applying..."
                        : "Apply settings"
                }
                submitIcon={
                    props.updateSettingsMutation.isPending
                        ? ReloadIcon
                        : SettingsIcon
                }
                canDiscard
                onReset={handleDiscard}
                disabled={() => isDisabled}
            >
                <Grid
                    gap="sm"
                    columns={{
                        base: 1,
                        lg: 1,
                    }}
                >
                    <GridItem>
                        <Card
                            title={<SectionHeading title="Pipeline" description="Camera and processing rate." />}
                            titleSeparator={false}
                            cardStyles="safeguard-settings-card"
                            height="full"
                        >
                            <Grid gap="sm">
                                <FormField
                                    form={form}
                                    name="fps"
                                    label="Frames per second"
                                    fullWidth
                                    render={(field) => (
                                        <Input
                                            {...field}
                                            type="number"
                                            min={1}
                                            step="1"
                                            autoComplete="off"
                                            disabled={
                                                props.updateSettingsMutation
                                                    .isPending
                                            }
                                        />
                                    )}
                                />
                                <FormField
                                    form={form}
                                    name="auto_calibration_enabled"
                                    label="Auto-calibration"
                                    fullWidth
                                    render={(field) => (
                                        <Checkbox
                                            {...field}
                                            id={field.name}
                                            label="Enable auto-calibration"
                                            disabled={
                                                props.updateSettingsMutation
                                                    .isPending
                                            }
                                        />
                                    )}
                                />
                                <FormField
                                    form={form}
                                    name="generic_object_detection_enabled"
                                    label="Generic object detection"
                                    fullWidth
                                    render={(field) => (
                                        <Checkbox
                                            {...field}
                                            id={field.name}
                                            label="Enable generic object detection"
                                            disabled={
                                                props.updateSettingsMutation
                                                    .isPending
                                            }
                                        />
                                    )}
                                />
                                <FormField
                                    form={form}
                                    name="ground_refit_mode"
                                    label="Ground re-fit mode"
                                    fullWidth
                                    render={(field) => {
                                        const detectionDisabled = !form.watch(
                                            "generic_object_detection_enabled",
                                        );
                                        const select = (
                                            <Select
                                                {...field}
                                                disabled={
                                                    detectionDisabled ||
                                                    props.updateSettingsMutation
                                                        .isPending
                                                }
                                                items={[
                                                    { value: "STATIC", component: "Static (fixed camera)" },
                                                    { value: "DYNAMIC", component: "Dynamic (moving camera)" },
                                                ]}
                                            />
                                        );
                                        if (detectionDisabled) {
                                            return (
                                                <Tooltip content="Enable generic object detection to configure.">
                                                    {select}
                                                </Tooltip>
                                            );
                                        }
                                        return select;
                                    }}
                                />
                                <SubLabel
                                    text={
                                        <>
                                            <div><strong>Static (fixed camera):</strong> caches the plane after first detection; re-fits only on IMU drift.</div>
                                            <div><strong>Dynamic (moving camera):</strong> re-fits the ground plane continuously.</div>
                                        </>
                                    }
                                />
                            </Grid>
                        </Card>
                    </GridItem>
                    <GridItem>
                        <Card
                            title={<SectionHeading title="Timing" description="Alert transition delays in seconds." />}
                            titleSeparator={false}
                            cardStyles="safeguard-settings-card"
                            height="full"
                        >
                            <Grid
                                gap="sm"
                                columns={{
                                    base: 1,
                                    md: 2,
                                }}
                            >
                                <FormField
                                    form={form}
                                    name="awareness_escalation_sec"
                                    label="Escalation (sec)"
                                    fullWidth
                                    render={(field) => (
                                        <Input
                                            {...field}
                                            type="number"
                                            min={1}
                                            step="1"
                                            autoComplete="off"
                                            disabled={
                                                props.updateSettingsMutation
                                                    .isPending
                                            }
                                        />
                                    )}
                                />
                                <FormField
                                    form={form}
                                    name="deescalation_sec"
                                    label="De-escalation (sec)"
                                    fullWidth
                                    render={(field) => (
                                        <Input
                                            {...field}
                                            type="number"
                                            min={1}
                                            step="1"
                                            autoComplete="off"
                                            disabled={
                                                props.updateSettingsMutation
                                                    .isPending
                                            }
                                        />
                                    )}
                                />
                            </Grid>
                        </Card>
                    </GridItem>
                    <GridItem>
                        <Card
                            title={<SectionHeading title="Events" description="Choose which event levels are kept while the app runs." />}
                            titleSeparator={false}
                            cardStyles="safeguard-settings-card"
                            height="full"
                        >
                            <Grid
                                gap="sm"
                                columns={{
                                    base: 1,
                                    md: 2,
                                }}
                            >
                                <FormField
                                    form={form}
                                    name="save_warning_events"
                                    label="Warning events"
                                    fullWidth
                                    render={(field) => (
                                        <Checkbox
                                            {...field}
                                            id={field.name}
                                            label="Keep warning events"
                                            disabled={
                                                props.updateSettingsMutation
                                                    .isPending
                                            }
                                        />
                                    )}
                                />
                                <FormField
                                    form={form}
                                    name="save_danger_events"
                                    label="Danger events"
                                    fullWidth
                                    render={(field) => (
                                        <Checkbox
                                            {...field}
                                            id={field.name}
                                            label="Keep danger events"
                                            disabled={
                                                props.updateSettingsMutation
                                                    .isPending
                                            }
                                        />
                                    )}
                                />
                                <FormField
                                    form={form}
                                    name="event_video_pre_trigger_sec"
                                    label="Pre-trigger video length (sec)"
                                    fullWidth
                                    render={(field) => (
                                        <Input
                                            {...field}
                                            type="number"
                                            min={0}
                                            step="1"
                                            autoComplete="off"
                                            disabled={
                                                props.updateSettingsMutation
                                                    .isPending
                                            }
                                        />
                                    )}
                                />
                                <FormField
                                    form={form}
                                    name="event_video_max_duration_sec"
                                    label="Max event video length (sec)"
                                    fullWidth
                                    render={(field) => (
                                        <Input
                                            {...field}
                                            type="number"
                                            min={1}
                                            step="1"
                                            autoComplete="off"
                                            disabled={
                                                props.updateSettingsMutation
                                                    .isPending
                                            }
                                        />
                                    )}
                                />
                                <FormField
                                    form={form}
                                    name="event_retention_count"
                                    label="Max recent events"
                                    fullWidth
                                    render={(field) => (
                                        <Input
                                            {...field}
                                            type="number"
                                            min={1}
                                            step="1"
                                            autoComplete="off"
                                            disabled={
                                                props.updateSettingsMutation
                                                    .isPending
                                            }
                                        />
                                    )}
                                />
                            </Grid>
                        </Card>
                    </GridItem>
                    <GridItem>
                        <ZoneFields
                            form={form}
                            name="danger_roi"
                            label="Danger zone"
                            disabled={props.updateSettingsMutation.isPending}
                        />
                    </GridItem>
                    <GridItem>
                        <ZoneFields
                            form={form}
                            name="warning_roi"
                            label="Warning zone"
                            disabled={props.updateSettingsMutation.isPending}
                        />
                    </GridItem>
                </Grid>
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
            <Card cardStyles="safeguard-settings-card">
                <Flex
                    direction="column"
                    gap="xs"
                    alignItems="center"
                    p="sm"
                    justifyContent="center"
                >
                    <CircleLoader mb="md" />
                    <SubHeader text="Loading settings" />
                    <SubLabel text="Waiting for the SafeGuard settings service to become available." />
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
