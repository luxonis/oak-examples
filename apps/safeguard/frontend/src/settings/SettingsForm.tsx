import {
	Alert,
	Button,
	Card,
	Checkbox,
	Form,
	FormField,
	Icon,
	Input,
	LoaderIcon,
	SubHeader,
	SubLabel,
	type UseFormReturn,
	useForm,
} from '@luxonis/ui-components';
import {
	type Settings,
	type SettingsFormValues,
	settingsSchema,
} from './settingsSchema';
import { useSettings } from './useSettings';

type ZoneFieldName = 'danger_roi' | 'warning_roi';
type UpdateSettingsMutation = ReturnType<
	typeof useSettings
>['updateSettingsMutation'];

function ZoneFields(props: {
	form: UseFormReturn<SettingsFormValues>;
	name: ZoneFieldName;
	label: string;
	disabled: boolean;
}) {
	return (
		<Card
			variant="outline"
			intent="gray"
			title={props.label}
			subtitle="Distance and horizontal bounds relative to the camera center."
			titleSeparator={false}
			fullWidth
		>
			<div className="flex flex-col gap-2">
				<SubLabel text="Negative x is left of center. Positive x is right of center." />
				<div className="grid grid-cols-3 gap-3">
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
				</div>
			</div>
		</Card>
	);
}

function SettingsFormInner(props: {
	settings: Settings;
	updateSettingsMutation: UpdateSettingsMutation;
}) {
	const form = useForm<SettingsFormValues>(
		settingsSchema,
		props.settings,
		'all',
	);
	const isPending = props.updateSettingsMutation.isPending;

	const handleApply = (values: SettingsFormValues) => {
		props.updateSettingsMutation.reset();
		props.updateSettingsMutation.mutate(values);
	};

	const handleDiscard = () => {
		form.reset();
		props.updateSettingsMutation.reset();
	};

	return (
		<div className="flex w-full flex-col gap-2">
			{props.updateSettingsMutation.error ? (
				<Alert
					variant="light"
					intent="error"
					title="Could not apply settings"
					description={props.updateSettingsMutation.error.message}
				/>
			) : null}
			<Form
				form={form}
				onSubmit={handleApply}
				submitLabel={isPending ? 'Applying…' : 'Apply settings'}
				actions={
					<Button
						type="button"
						variant="outline"
						label="Discard"
						disabled={isPending || !form.formState.isDirty}
						onClick={handleDiscard}
					/>
				}
				disabled={
					isPending || !form.formState.isDirty || !form.formState.isValid
				}
			>
				<div className="flex flex-col gap-4">
					<Card
						variant="outline"
						intent="gray"
						title="Pipeline"
						subtitle="Camera and processing rate."
						titleSeparator={false}
						fullWidth
					>
						<div className="flex flex-col gap-3">
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
										disabled={isPending}
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
										disabled={isPending}
									/>
								)}
							/>
						</div>
					</Card>
					<Card
						variant="outline"
						intent="gray"
						title="Timing"
						subtitle="Alert transition delays in seconds."
						titleSeparator={false}
						fullWidth
					>
						<div className="grid grid-cols-2 gap-3">
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
										disabled={isPending}
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
										disabled={isPending}
									/>
								)}
							/>
						</div>
					</Card>
					<ZoneFields
						form={form}
						name="danger_roi"
						label="Danger zone"
						disabled={isPending}
					/>
					<ZoneFields
						form={form}
						name="warning_roi"
						label="Warning zone"
						disabled={isPending}
					/>
				</div>
			</Form>
		</div>
	);
}

function SettingsForm() {
	const { settingsQuery, updateSettingsMutation } = useSettings();

	if (settingsQuery.error) {
		return (
			<Alert
				variant="light"
				intent="error"
				title="Could not load settings"
				description={settingsQuery.error.message}
				actions={
					<Button
						type="button"
						variant="outline"
						intent="white"
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
			<Card variant="outline" intent="gray" fullWidth>
				<div className="flex flex-col items-center justify-center gap-1 p-3">
					<Icon icon={LoaderIcon} size="lg" className="mb-3 animate-spin" />
					<SubHeader text="Loading settings" />
					<SubLabel text="Waiting for the SafeGuard settings service to become available." />
				</div>
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
